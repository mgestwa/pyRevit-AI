#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP (Model Context Protocol) utilities for interacting with Claude AI
"""

import os
import json
import requests
from pyrevit import script

# Constants
CLAUDE_API_ENDPOINT = "https://api.anthropic.com/v1/messages"
# API key hardcoded directly in the code
CLAUDE_API_KEY = "xxxxxxxx"  # Zastąp właściwym kluczem API


def sanitize_value(value):
    """
    Sanitize a value to ensure it can be properly encoded in JSON
    
    Args:
        value: Any value that might need sanitization
        
    Returns:
        Sanitized value suitable for JSON serialization
    """
    if isinstance(value, str) or isinstance(value, unicode):
        try:
            # Try to decode as utf-8 if it's a byte string
            if isinstance(value, str):
                return value.decode('utf-8', 'replace')
            return value
        except UnicodeError:
            # Replace problematic characters with '?'
            return unicode(str(value), 'utf-8', 'replace')
    elif isinstance(value, (int, float, bool, type(None))):
        return value
    elif isinstance(value, dict):
        result = {}
        for k, v in value.items():
            result[sanitize_value(k)] = sanitize_value(v)
        return result
    elif isinstance(value, (list, tuple)):
        return [sanitize_value(item) for item in value]
    else:
        # For any other types, convert to string and sanitize
        try:
            return str(value)
        except:
            return "Unsupported value type"


def create_model_context(elements_data):
    """
    Create Model Context Protocol structure from Revit elements data
    
    Args:
        elements_data: List of dictionaries containing element information
        
    Returns:
        Dictionary with MCP structure
    """
    # Create the basic MCP dictionary structure
    mcp_data = {
        "model_context": {
            "title": "Revit Building Model Analysis",
            "description": "Information about selected elements from a Revit building model",
            "model_type": "building_information_model",
            "elements": []
        }
    }
    
    # Add each element to the MCP structure
    for element in elements_data:
        # Sanitize all element data
        sanitized_element = sanitize_value(element)
        
        mcp_element = {
            "id": str(sanitized_element["id"]),
            "type": sanitized_element["type"],
            "category": sanitized_element["category"],
            "properties": sanitized_element["parameters"]
        }
        
        # Add relationships if they exist (not implemented in this simple example)
        mcp_element["relationships"] = []
        
        mcp_data["model_context"]["elements"].append(mcp_element)
    
    return mcp_data


def send_to_claude(model_context, user_query):
    """
    Send the model context and user query to Claude AI
    
    Args:
        model_context: Dictionary with MCP data structure
        user_query: User's query about the Revit elements
        
    Returns:
        Claude's response text
    """
    if not CLAUDE_API_KEY or CLAUDE_API_KEY == "YOUR_CLAUDE_API_KEY_HERE":
        return "Error: Please replace the placeholder with your actual Claude API key in the mcp_utils.py file."
    
    try:
        # Create the context message
        context_message = json.dumps(model_context, indent=2, ensure_ascii=True)
        
        # Define the system prompt instructing Claude how to use the MCP data
        system_prompt = """
        You are an expert BIM consultant specializing in Revit models.
        A user has shared element data from their Revit model with you through the Model Context Protocol format.
        Answer the user's question by analyzing the provided model data.
        Be specific and reference the element IDs, types, categories, and parameters in your answer when relevant.
        If the necessary information is not available in the provided data, explain what additional data would be needed.
        """
        
        # Prepare the request payload
        payload = {
            "model": "xxxxxxxx",
            "max_tokens": 1000,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": context_message
                        },
                        {
                            "type": "text",
                            "text": sanitize_value(user_query)
                        }
                    ]
                }
            ]
        }
        
        # Set headers
        headers = {
            "Content-Type": "application/json",
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "xxxxxxxx"
        }
        
        # Send the request to Claude API
        response = requests.post(
            CLAUDE_API_ENDPOINT,
            headers=headers,
            json=payload
        )
        
        # Parse the response
        if response.status_code == 200:
            result = response.json()
            return result.get("content", [{}])[0].get("text", "No response text found")
        else:
            return "Error: API request failed with status code %s\n%s" % (response.status_code, response.text)
    
    except Exception as e:
        return "Error: %s" % str(e)


# For testing purposes
if __name__ == "__main__":
    print("MCP Utilities module - import this in the main script") 