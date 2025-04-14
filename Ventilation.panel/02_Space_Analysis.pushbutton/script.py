#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Space Analysis and Ventilation Requirements Module
Analyzes spaces in the Revit model, determines air exchange rates,
and calculates required ventilation flow rates

This is a refactored and optimized version with additional comments for clarity.
Designed to be compatible with Python 2.7 as used by PyRevit.
"""

# Imports from __future__ must be at the beginning of the file
from __future__ import print_function
from __future__ import with_statement

__title__ = "Space\nAnalysis"
__author__ = "Claude AI"

import os
import sys
import json
import clr
from System.Collections.Generic import List
import requests

# Referencje do API Revita
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')
from Autodesk.Revit.DB import *
from Autodesk.Revit.DB.Mechanical import *
from Autodesk.Revit.UI import TaskDialog

# Import modułów PyRevit
from pyrevit import forms
from pyrevit import script

# Konfiguracja API (możesz to zmienić na innego dostawcę LLM)
CLAUDE_API_KEY = "xxxxxxxx"  # Replace with your Claude API key
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"

# Pobierz aktywny dokument Revit
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

# Cache dla wyników LLM, aby nie powtarzać zapytań dla tych samych typów pomieszczeń
LLM_CACHE = {}

# Cache dla typów przestrzeni zidentyfikowanych przez LLM
SPACE_TYPE_CACHE = {}

def call_claude_api(prompt, max_tokens, temperature):
    """Helper function to call the Claude API with a given prompt."""
    global CLAUDE_API_KEY, CLAUDE_API_URL
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "xxxxxxxx",
        "content-type": "application/json"
    }
    data = {
        "model": "xxxxxxxx",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    try:
        response = requests.post(CLAUDE_API_URL, headers=headers, json=data)
        response_data = response.json()
        if "content" in response_data and len(response_data["content"]) > 0:
            return response_data["content"][0]["text"].strip()
    except Exception as e:
        script.get_logger().error("Claude API error: {}".format(e))
    return None

def query_llm_for_air_exchange_rate(space_type):
    """Queries the language model (Claude) to determine the air exchange rate for a given space type."""
    if space_type in LLM_CACHE:
        return LLM_CACHE[space_type]

    global CLAUDE_API_KEY
    if not CLAUDE_API_KEY:
        result = forms.ask_for_string(
            default="",
            prompt="Enter Claude API key (needed to determine air exchange rate):",
            title="API Configuration"
        )
        if result:
            CLAUDE_API_KEY = result
        else:
            script.get_logger().warning("No API key provided. Using default air exchange rate.")
            return 1.0

    prompt = (
        "Provide the recommended air exchange rate (1/h) for a space of type '{}' "
        "in a building according to HVAC standards. Answer only with a floating-point number, e.g., 2.5"
    ).format(space_type)
    
    answer = call_claude_api(prompt, 20, 0.3)
    if answer:
        try:
            rate = float(answer)
            LLM_CACHE[space_type] = rate
            return rate
        except ValueError:
            script.get_logger().warning("Failed to convert Claude response to number: {}".format(answer))
    return 1.0

def get_spaces():
    """Retrieves all MEP spaces or architectural rooms from the Revit model."""
    try:
        # First try to get MEP spaces
        spaces = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_MEPSpaces).WhereElementIsNotElementType().ToElements()
        
        # If no MEP spaces, fallback to architectural rooms
        if not spaces or len(spaces) == 0:
            script.get_logger().info("No MEP spaces found. Trying to get architectural rooms.")
            spaces = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms).WhereElementIsNotElementType().ToElements()
        
        if spaces and len(spaces) > 0:
            script.get_logger().info("Found {} spaces/rooms.".format(len(spaces)))
        else:
            script.get_logger().warning("No spaces or rooms found.")
        
        return spaces
    except Exception as e:
        script.get_logger().error("Error while getting spaces: {}".format(e))
        return []

def get_space_name(space):
    """Helper function to get the name of a space or room across different Revit versions."""
    try:
        # First, try the direct Name property
        if hasattr(space, "Name"):
            return space.Name
        
        # Next, try the get_Name() method
        if hasattr(space, "get_Name"):
            return space.get_Name()
        
        # Attempt to retrieve the 'Name' parameter
        name_param = space.LookupParameter("Name")
        if name_param and name_param.HasValue:
            return name_param.AsString()
        
        # Attempt to retrieve the 'Room Name' parameter
        room_name_param = space.LookupParameter("Room Name")
        if room_name_param and room_name_param.HasValue:
            return room_name_param.AsString()
        
        # As a last resort, iterate through possible parameters
        if hasattr(space, "get_Parameter"):
            for param_name in ["Name", "Room Name"]:
                param = space.get_Parameter(param_name)
                if param and param.HasValue:
                    return param.AsString()
        
        return "Unnamed Space"
    except Exception:
        return "Unnamed Space"

def get_space_type(space):
    """Determines the space type based on parameters or by querying Claude AI."""
    # Check common parameters for space type
    for param_name in ["Space Type", "Typ pomieszczenia", "Room Type", "Function", "Department"]:
        param = space.LookupParameter(param_name)
        if param and param.HasValue and param.AsString():
            return param.AsString()
    
    # Fallback: use the space name and cache lookup
    name = get_space_name(space)
    if name in SPACE_TYPE_CACHE:
        return SPACE_TYPE_CACHE[name]
    
    # Formulate an enhanced prompt for accurate classification
    prompt = (
        "You are a building information modeling expert specializing in HVAC and MEP systems. "
        "Based on the space name '{}' in a building model, determine the most accurate space type category. "
        "Consider architectural conventions, building codes, and standard room classification systems in your determination. "
        "\n\nClassify the space as one of the following standard types: "
        "Office, Open Office, Executive Office, Conference Room, Meeting Room, Training Room, "
        "Kitchen, Pantry, Cafeteria, Restaurant, Dining Room, "
        "Bathroom, Restroom, Toilet, Shower Room, "
        "Corridor, Hallway, Lobby, Entrance, Vestibule, "
        "Bedroom, Dormitory, Hotel Room, "
        "Living Room, Lounge, Waiting Area, "
        "Classroom, Lecture Hall, Educational Space, "
        "Retail Space, Store, Shop, "
        "Server Room, IT Room, Data Center, "
        "Archive, Records Room, "
        "Storage, Closet, Utility Room, "
        "Gym, Fitness Center, "
        "Gymnasium, Sports Hall, "
        "Locker Room, Changing Room, "
        "Laundry, "
        "Garage, Parking, "
        "Workshop, Maintenance Room, "
        "Laboratory, Research Space, "
        "Medical Examination Room, Treatment Room, "
        "Office Support, Copy Room, Mail Room, "
        "Mechanical Room, Electrical Room, "
        "Stairwell, Elevator, "
        "Atrium, "
        "Auditorium, Theater, "
        "Library, Reading Room, "
        "Child Care, Nursery, "
        "Janitor Closet, "
        "Loading Dock, "
        "Outdoor Space, Terrace, Balcony."
        "\n\nIf none of these match well, select the closest standard category or respond with 'Other'. "
        "Respond ONLY with the selected space type, without any explanation or additional text."
    ).format(name)
    
    space_type = call_claude_api(prompt, 20, 0.1)
    if space_type:
        SPACE_TYPE_CACHE[name] = space_type
        return space_type
    return "Other"

def get_air_exchange_rate(space_type):
    """Returns the air exchange rate for a given space type using Claude."""
    return query_llm_for_air_exchange_rate(space_type)

def calculate_required_air_flow(volume, air_exchange_rate):
    """Calculates the required air flow in m³/h based on volume and air exchange rate."""
    return volume * air_exchange_rate

def get_unit_conversion_factor():
    """Determines the unit conversion factors (length, area, volume) based on the project's units."""
    try:
        units = doc.GetUnits()
        
        # Modern Revit API (Revit 2021+)
        if hasattr(units, "GetFormatOptions"):
            length_format = units.GetFormatOptions(UnitType.UT_Length)
            if hasattr(length_format, "GetUnitTypeId"):
                if "meter" in str(length_format.GetUnitTypeId()).lower():
                    return {"length": 1.0, "area": 1.0, "volume": 1.0}
        
        # Older versions of Revit
        if hasattr(units, "GetDisplayUnitType"):
            length_unit = units.GetDisplayUnitType(UnitType.UT_Length)
            if "meter" in str(length_unit).lower():
                return {"length": 1.0, "area": 1.0, "volume": 1.0}
        
        # Default: assume imperial units requiring conversion
        return {"length": 0.3048, "area": 0.092903, "volume": 0.0283168}
    except Exception:
        return {"length": 0.3048, "area": 0.092903, "volume": 0.0283168}

def assign_air_flow_to_space(space, required_air_flow):
    """Assigns the calculated required air flow (in m³/h) to the 'Specified Supply Airflow' parameter in the space."""
    t = None  # Initialize transaction variable
    try:
        t = Transaction(doc, "Set Required Air Flow")
        t.Start()
        
        # Convert from m³/h to ft³/s (conversion factor provided)
        airflow_converted = required_air_flow * 0.0098097
        
        script.get_logger().info("Setting airflow for space: {}".format(space.Id.IntegerValue))
        script.get_logger().info("Original airflow value (m³/h): {}".format(required_air_flow))
        script.get_logger().info("Converted airflow value (m³/s): {}".format(airflow_converted))
        
        param_set = False
        
        # Attempt to set the parameter using LookupParameter
        airflow_param = space.LookupParameter("Specified Supply Airflow")
        if airflow_param and not airflow_param.IsReadOnly:
            script.get_logger().info("Found 'Specified Supply Airflow' parameter using LookupParameter")
            airflow_param.Set(airflow_converted)
            param_set = True
            script.get_logger().info("Successfully set 'Specified Supply Airflow' to {}".format(airflow_converted))
        
        # Fallback: try setting a built-in parameter
        if not param_set:
            try:
                room_supply_param = space.get_Parameter(BuiltInParameter.ROOM_DESIGN_SUPPLY_AIRFLOW_PARAM)
                if room_supply_param and not room_supply_param.IsReadOnly:
                    script.get_logger().info("Found built-in parameter ROOM_DESIGN_SUPPLY_AIRFLOW_PARAM")
                    room_supply_param.Set(airflow_converted)
                    param_set = True
                    script.get_logger().info("Successfully set built-in parameter to {}".format(airflow_converted))
            except Exception as e:
                script.get_logger().debug("Could not set built-in parameter: {}".format(e))
        
        if param_set:
            t.Commit()
            script.get_logger().info("Successfully set airflow parameter")
            return True
        else:
            script.get_logger().warning("Could not find or set the airflow parameter")
            t.RollBack()
            return False
    except Exception as e:
        if t is not None and t.HasStarted() and not t.HasEnded():
            t.RollBack()
        script.get_logger().error("Error assigning air flow to space: {}".format(e))
        return False

def analyze_space(space):
    """Analyzes a single space to determine its ventilation requirements and returns a dictionary of results."""
    try:
        conversion = get_unit_conversion_factor()
        name = get_space_name(space)
        
        # Retrieve room number; fallback to element ID if not found
        number = ""
        if hasattr(space, "Number"):
            number = space.Number
        elif hasattr(space, "get_Number"):
            number = space.get_Number()
        else:
            number_param = space.LookupParameter("Number")
            if number_param and number_param.HasValue:
                number = number_param.AsString()
            else:
                number = space.Id.IntegerValue
        
        # Determine area from property or parameter
        if hasattr(space, "Area"):
            area = space.Area * conversion["area"]
        else:
            area_param = space.LookupParameter("Area") or space.LookupParameter("Powierzchnia")
            if area_param and area_param.HasValue:
                area = area_param.AsDouble() * conversion["area"]
            else:
                raise ValueError("Cannot determine space area")
        
        # Determine height and volume
        if hasattr(space, "Volume") and space.Volume > 0 and area > 0:
            volume = space.Volume * conversion["volume"]
            height = volume / area
        else:
            height_param = space.LookupParameter("Height") or space.LookupParameter("Wysokość")
            if height_param and height_param.HasValue:
                height = height_param.AsDouble() * conversion["length"]
            else:
                height = 3.0  # Default height in meters
            volume = area * height
        
        # Determine space type and corresponding air exchange rate
        space_type = get_space_type(space)
        air_exchange_rate = get_air_exchange_rate(space_type)
        required_air_flow = calculate_required_air_flow(volume, air_exchange_rate)
        
        # Compile analysis results
        result = {
            "id": space.Id.IntegerValue if hasattr(space.Id, "IntegerValue") else str(space.Id),
            "name": name,
            "number": number,
            "area": area,
            "height": height,
            "volume": volume,
            "space_type": space_type,
            "air_exchange_rate": air_exchange_rate,
            "required_air_flow": required_air_flow,
            "element": space
        }
        
        return result
    except Exception as e:
        script.get_logger().error("Error during space analysis: {}".format(e))
        return None

def save_results(analyses):
    """Saves the analysis results to a JSON file in the user's Documents folder."""
    import json
    import os
    
    # Determine the target directory within Documents
    documents_dir = os.path.join(os.path.expanduser("~"), "Documents")
    target_dir = os.path.join(documents_dir, "pyrevit_ventilation_data")

    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    serializable_analyses = []
    for analysis in analyses:
        serializable_analysis = dict(analysis)
        if 'element' in serializable_analysis:
            del serializable_analysis['element']
        serializable_analyses.append(serializable_analysis)

    target_file = os.path.join(target_dir, "ventilation_analysis.json")
    
    with open(target_file, 'w') as f:
        json.dump(serializable_analyses, f, indent=2)

    return target_file

def main():
    """Main function that orchestrates space analysis, user selection, and parameter assignment."""
    spaces = get_spaces()
    
    if not spaces or len(spaces) == 0:
        forms.alert("No spaces found in the model. Make sure the model contains MEP spaces or rooms.", title="No Spaces")
        return
    
    space_analyses = []
    for space in spaces:
        analysis = analyze_space(space)
        if analysis:
            space_analyses.append(analysis)
    
    if not space_analyses:
        forms.alert("Failed to analyze any spaces.", title="No Data")
        return
    
    headers = ["Number", "Name", "Type", "Area [m²]", "Volume [m³]", "Air Exchange Rate [1/h]", "Flow Rate [m³/h]"]
    data = []
    
    for analysis in space_analyses:
        data.append([
            analysis["number"],
            analysis["name"],
            analysis["space_type"],
            "{:.2f}".format(analysis["area"]),
            "{:.2f}".format(analysis["volume"]),
            "{:.1f}".format(analysis["air_exchange_rate"]),
            "{:.2f}".format(analysis["required_air_flow"])
        ])
    
    selected = forms.SelectFromList.show(data, 
                                         title="Space Analysis and Ventilation Requirements",
                                         button_name="Save Results",
                                         multiselect=True,
                                         column_names=headers)
    
    if selected:
        selected_indices = [data.index(item) for item in selected]
        selected_analyses = [space_analyses[i] for i in selected_indices]
        
        assign_to_params = forms.alert(
            "Do you want to assign the calculated airflow values to Revit space parameters?",
            title="Assign to Parameters",
            yes=True, no=True
        )
        
        if assign_to_params:
            success_count = 0
            for analysis in selected_analyses:
                if assign_air_flow_to_space(analysis["element"], analysis["required_air_flow"]):
                    success_count += 1
            
            if success_count > 0:
                forms.alert("Assigned air flow values to {} out of {} spaces.".format(success_count, len(selected_analyses)), 
                           title="Values Assigned")
        
        temp_file = save_results(selected_analyses)
        
        forms.alert("Analysis results have been saved to file:\n {} \n\nYou can now use other modules for ventilation design.".format(temp_file), 
                   title="Analysis Complete")

if __name__ == "__main__":
    main() 