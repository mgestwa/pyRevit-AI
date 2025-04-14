#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP Tool for Revit
Uses Claude's Model Context Protocol to assist with Revit model analysis
"""

__title__ = "MCP\nAssistant"
__author__ = "Claude AI"

import os
import sys
import json
import clr
from System.Collections.Generic import List

# Add references to Revit API
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')
from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import TaskDialog

# Import PyRevit modules
from pyrevit import forms
from pyrevit import script

# Import MCP utilities
from mcp_utils import create_model_context, send_to_claude, sanitize_value

# Get the current Revit document
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument


def get_selected_elements():
    """Get currently selected elements in Revit"""
    selection = uidoc.Selection.GetElementIds()
    return [doc.GetElement(element_id) for element_id in selection]


def analyze_elements(elements):
    """Extract relevant information from Revit elements"""
    elements_data = []
    
    for element in elements:
        try:
            # Get element type and parameters
            element_type = element.GetType().Name
            category = getattr(element, "Category", None)
            category_name = category.Name if category else "No Category"
            
            # Get parameters
            parameters = {}
            for param in element.Parameters:
                try:
                    param_name = param.Definition.Name
                    storage_type = param.StorageType
                    
                    # Get parameter value based on storage type
                    if storage_type == StorageType.String:
                        param_value = param.AsString()
                    elif storage_type == StorageType.Integer:
                        param_value = param.AsInteger()
                    elif storage_type == StorageType.Double:
                        param_value = param.AsDouble()
                    elif storage_type == StorageType.ElementId:
                        param_value = str(param.AsElementId().IntegerValue)
                    else:
                        param_value = "Unknown storage type"
                    
                    # Sanitize parameter value to ensure it can be encoded to JSON
                    parameters[param_name] = param_value
                except Exception as param_ex:
                    # If we can't get a parameter, skip it
                    script.get_logger().error("Error getting parameter: %s" % str(param_ex))
            
            element_data = {
                "id": element.Id.IntegerValue,
                "type": element_type,
                "category": category_name,
                "parameters": parameters
            }
            
            elements_data.append(element_data)
        except Exception as ex:
            script.get_logger().error("Error analyzing element: %s" % str(ex))
    
    return elements_data


def main():
    # Get selected elements
    selected_elements = get_selected_elements()
    
    if not selected_elements:
        forms.alert("Please select elements in the Revit model first.", title="No Selection")
        return
    
    # Analyze elements
    elements_data = analyze_elements(selected_elements)
    
    if not elements_data:
        forms.alert("Could not extract any data from the selected elements.", title="No Data")
        return
    
    # Create model context for Claude
    model_context = create_model_context(elements_data)
    
    # Prompt user for query
    user_query = forms.ask_for_string(
        prompt="What would you like to ask about the selected elements?",
        title="Claude MCP Assistant"
    )
    
    if not user_query:
        return
    
    # Show progress
    with forms.ProgressBar(title="Processing with Claude") as pb:
        pb.update_progress(10, 100)
        
        # Send to Claude API
        response = send_to_claude(model_context, user_query)
        
        pb.update_progress(100, 100)
    
    # Show results
    forms.alert(response, title="Claude MCP Analysis")


if __name__ == "__main__":
    main() 