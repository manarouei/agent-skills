import re
import base64
from urllib.parse import urlencode
from typing import Dict, List, Optional, Any
from datetime import datetime ,timedelta, timezone
import logging
import time
from zoneinfo import ZoneInfo
import requests
from utils import googleCalendar_norm
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)



class GoogleCalendarNode(BaseNode):
    """
    Google Calendar node for managing calendar events and availability
    """
    # ======================= Node metadata & properties =======================
    type = "googleCalendar"
    version = 1.3
    
    description = {
        "displayName": "Google Calendar",
        "name": "googleCalendar",
        "icon": "file:googleCalendar.svg",
        "group": ["input"],
        "description": "Consume Google Calendar API",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "usableAsTool": True,
        "credentials": [
            {
                "name": "googleCalendarApi",
                "required": True
            }
        ]
    }
    
    # ===== n8n-style PROPERTIES (Python) =====
    properties = {
        "parameters": [
            # ---- Resource switcher (calendar | event) ----
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Resource",
                "options": [
                    {"name": "Calendar", 
                     "value": "calendar"
                     },
                    {"name": "Event",    
                     "value": "event"
                     }
                ],
                "default": "event",
                "description": "The resource to operate on",
            },

            # --------------------- CALENDAR ---------------------
            # calendar.operations (availability)
            {
                "display_name": "Operation",
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "noDataExpression": True,
                "display_options": {"show": {"resource": ["calendar"]}},
                "options": [
                    {
                        "name": "Availability",
                        "value": "availability",
                        "type": NodeParameterType.OPTIONS,
                        "description": "If a time-slot is available in a calendar",
                        "display_options": {"show": {"resource": ["calendar"]}},
                        "action": "Get availability in a calendar",
                    },
                ],
                "default": "availability",

                "description": "Check if a time-slot is available in a calendar"
            },

            # calendar.fields
            {
                "display_name": "Calendar",
                "name": "calendar",
                "type": NodeParameterType.RESOURCE_LOCATOR,
                "display_options": {"show": {"resource": ["calendar"]}},
                "default": {"mode": "list", 
                            "value": ""},
                "required": True,
                "description": "Google Calendar to operate on",
                "modes": [
                    {
                        "displayName": "Calendar",
                        "name": "list",
                        "type": NodeParameterType.ARRAY,
                        "description": "Select a calendar from the list",
                        "display_options": {"show": {"resource": ["calendar"]}},
                        "placeholder": "Select a Calendar...",
                        "typeOptions": {"searchListMethod": "getCalendars", "searchable": True},
                    },
                    {
                        "displayName": "ID",
                        "name": "id",
                        "type": NodeParameterType.STRING,
                        "description": "ID of the calendar",
                        "display_options": {"show": {"resource": ["calendar"]}},
                          "placeholder": "name@google.com",
                    },
                ],
                "display_options": {"show": {"resource": ["calendar"]}},
            },
            {
                "display_name": "Start Time",
                "name": "timeMin",
                "type": NodeParameterType.DATETIME,
                "required": True,
                "default": "",
                "description": "Start of the interval",
                "display_options": {"show": {"operation": ["availability"], "resource": ["calendar"], 
                                  
                                             }},
            },
            {
                "display_name": "End Time",
                "name": "timeMax",
                "type": NodeParameterType.DATETIME,
                "required": True,
                "default": "",
                "description": "End of the interval",
                "display_options": {"show": {"operation": ["availability"], "resource": ["calendar"]
                                         
                                             }},
            },
            
            {
                "display_name": "Options",
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "placeholder": "Add option",
                "default": {},
                "description": "Additional options for the request",
                "display_options": {"show": {"operation": ["availability"], 
                                             "resource": ["calendar"]}},
                "options": [
                    {
                        "displayName": "Output Format",
                        "name": "outputFormat",
                        "type": NodeParameterType.OPTIONS,
                        "description": "The format to return the data in",
                        "display_options": {"show": {"resource": ["calendar"]}},
                        "options": [ #fix
                            {"name": "Availability", 
                             "value": "availability", 
                             "type": NodeParameterType.OPTIONS,
                            "display_options": 
                            {"show": {"resource": ["calendar"]}},
                             "description": "Boolean free/busy"},

                            {"name": "Booked Slots", 
                             "value": "bookedSlots", 
                             "type": NodeParameterType.OPTIONS,
                            "display_options": {"show": {"resource": ["calendar"]}},
                             "description": "Return busy intervals"},

                            {"name": "RAW",          
                             "value": "raw",         
                             "type": NodeParameterType.OPTIONS,
                            "display_options": {"show": {"resource": ["calendar"]}},
                             "description": "Raw API response"},
                        ],
                        "default": "availability",
                        "display_options": {"show": {"resource": ["calendar"]}},
                        "description": "The format to return the data in",
                    },
                    {"name": "timezone", 
                     "type": NodeParameterType.OPTIONS, 
                    "description":"",
                    "display_options": {"show": {"resource": ["calendar"]}},
                     "display_name": "Timezone", 
                     "default": "UTC",
                     "options": [{"name": "UTC", 
                                  
                                "type": NodeParameterType.OPTIONS,
                                  "value": "UTC",
                                    "description":"",
                                    "display_options": {"show": {"resource": ["calendar"]}}}, 
                                 {"name": "Asia/Tehran", 
                                  "value": "Asia/Tehran",

                                    "type": NodeParameterType.OPTIONS,
                                    "description":"",
                                    "display_options": {"show": {"resource": ["calendar"]}},}]},
       
                ],
            },

            # ----------------------- EVENT -----------------------
            # event.operations
            {
                "display_name": "Operation",
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "noDataExpression": True,
                "description":"Select an operation to perform on the event",
                "display_options": {"show": {"resource": ["event"]}},
                "options": [
                    {"name": "Create",  
                     "value": "create",  
                     "description": "Add a event to calendar", 
                     "action": "Create an event"},

                    {"name": "Delete",  
                     "value": "delete",  
                     "description": "Delete an event",        
                     "action": "Delete an event"},

                    {"name": "Get",     
                     "value": "get",     
                     "description": "Retrieve an event",       
                     "action": "Get an event"},

                    {"name": "Get Many",
                     "value": "getAll",  
                     "description": "Retrieve many events from a calendar", 
                     "action": "Get many events"},

                    {"name": "Update",  
                     "value": "update",  
                     "description": "Update an event",          
                     "action": "Update an event"},
                ],
                "default": "create",
            },

            # Common calendar selector for event resource
            {
                "display_name": "Calendar",
                "name": "calendar",
                "type": NodeParameterType.RESOURCE_LOCATOR,
                "default": {"mode": "list", 
                            "value": ""},
                "required": True,
                "description": "Google Calendar to operate on",
                "display_options": {"show": {"resource": ["event"]}},
                "modes": [
                    {
                        "displayName": "Calendar",
                        "type": NodeParameterType.ARRAY,
                        "name": "list",
                        "description":"",
                        "placeholder": "Select a Calendar...",
                        "display_options": {"show": {"resource": ["event"]}},
                        "typeOptions": {"searchListMethod": "getCalendars", 
                                        "searchable": True},
                    },
                    {
                        "displayName": "ID",
                        "name": "id",
                        "description":"",
                        "type": NodeParameterType.STRING,
                        #FIXME  NodeParameterType.DATETIME,
                        "display_options": {"show": {"resource": ["event"]}},
                        "placeholder": "name@google.com",
                    },
                ],
                "display_options": {"show": {"resource": ["event"]}},
            },

            # -------- event:create --------
            {
                "display_name": "Start",
                "name": "start",
                "type": NodeParameterType.DATETIME,
                "required": True,
                "default": "={{ $now }}",
                "description": "Start time (expression or fixed)",
                "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
            },
            {
                "display_name": "End",
                "name": "end",
                "type": NodeParameterType.DATETIME,
                "required": True,
                "default": "={{ $now.plus(1, 'hour') }}",
                "description": "End time (expression or fixed)",
                "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
            },
            {
                "display_name": "Use Default Reminders",
                "name": "useDefaultReminders",
                "type": NodeParameterType.BOOLEAN,
                "default": True,
                "description":"",
                "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
            },
            {
                "display_name": "Additional Fields",
                "name": "additionalFields",
                "type": NodeParameterType.COLLECTION,
                "description":"",
                "placeholder": "Add Field",
                "default": {},
                "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                "options": [
                    {"displayName": "All Day",
                     "name": "allday",
                     "type": NodeParameterType.BOOLEAN, 
                     "description": "Whether the event is all day or not",
                     "default": True,
                     "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                     },
                    {
                        "displayName": "Attendees",
                        "name": "attendees",
                        "type": NodeParameterType.STRING,
                        "description":"",
                        "typeOptions": {"multipleValues": True, 
                                        "multipleValueButtonText": "Add Attendee"},
                        "default": "",
                        "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                        "description": "Emails (comma-separated or add multiple values)",
                    },
                    # {
                    #     "displayName": "Color Name or ID",
                    #     "name": "color",
                    #     "type": NodeParameterType.OPTIONS,
                    #     "typeOptions": {"loadOptionsMethod": "getColors"},
                    #     "default": "",
                    #     "description": "Pick or specify an ID via expression",
                    # },
                    {
                        "displayName": "Conference Data",
                        "name": "conferenceDataUi",
                        "type": NodeParameterType.COLLECTION,
                        "placeholder": "Add Conference",
                        "typeOptions": {"multipleValues": False},
                        "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                        "default": {},
                        "options": [
                            {
                                "displayName": "Conference Link",
                                "name": "conferenceDataValues",
                                "description":"",
                                #FIX TYPE?
                                "type": NodeParameterType.COLLECTION,
                                "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                                "values": [
                                    {
                                        "displayName": "Type Name or ID",
                                        "name": "conferenceSolution",
                                        "type": NodeParameterType.OPTIONS,
                                        "typeOptions": {"loadOptionsMethod": "getConferenceSolutions",
                                                         "loadOptionsDependsOn": ["calendar"]},
                                        "default": "",
                                        "description": "Meet/Hangouts etc.",
                                        "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}}
                                    },
                                ],
                            }
                        ],
                        "description": "Create a conference link and attach it to the event",
                    },
                    {"displayName": "Description", 
                     "name": "description", 
                     "type": NodeParameterType.STRING, 
                     "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                     "default": ""
                     },
                    {"displayName": 
                     "Guests Can Invite Others", 
                     "name": "guestsCanInviteOthers", 
                    "description":"",
                     "type": NodeParameterType.BOOLEAN, 
                     "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                     "default": True},

                    {"displayName": "Guests Can Modify",        
                     "name": "guestsCanModify",        
                    "description":"",
                     "type": NodeParameterType.BOOLEAN, 
                     "default": False
                     },
                    {"displayName": "Guests Can See Other Guests",
                     "name": "guestsCanSeeOtherGuests",
                    "description":"",
                     "type": NodeParameterType.BOOLEAN, 
                     "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                     "default": True},

                    {"displayName": "ID",          
                     "name": "id",        
                     "type": NodeParameterType.STRING,  
                     "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                     "default": "", 
                     "description": "Opaque identifier of the event"},
                     
                    {"displayName": "Location",    
                     "name": "location",  
                     "type": NodeParameterType.STRING,  
                    "description":"",
                     "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                     "default": ""},
                    {"displayName": "Max Attendees",
                     "name": "maxAttendees",
                     "type": NodeParameterType.NUMBER,
                    "description":"",
                     "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                     "default": 0,
                        "description": "If exceeded, only the participant is returned",
                    }, 
                    # {
                    #     "displayName": "Repeat Frequency",
                    #     "name": "repeatFrecuency",
                    #     "type": NodeParameterType.OPTIONS,
                    #     "description":"",
                    #     "display_options": {"show": {"operation": ["create"], 
                    #                          "resource": ["event"]}},
                    #     "options": [{"name":"Daily",
                    #                 "value":"Daily",
                    #                 "type": NodeParameterType.OPTIONS,
                    #                 "display_options": {"show": {"operation": ["create"], 
                    #                          "resource": ["event"]}},
                    #                 "description":""},
                    #                 {"name":"Weekly",
                    #                  "value":"weekly",
                    #                 "type": NodeParameterType.OPTIONS,
                    #                  "display_options": {"show": {"operation": ["create"], 
                    #                          "resource": ["event"]}},
                    #                  "description":""},
                    #                 {"name":"Monthly",
                    #                  "value":"monthly",
                    #                 "type": NodeParameterType.OPTIONS,
                    #                  "display_options": {"show": {"operation": ["create"], 
                    #                          "resource": ["event"]}},
                    #                  "description":""},
                    #                 {"name":"Yearly",
                    #                  "value":"yearly",
                    #                 "type": NodeParameterType.OPTIONS,
                    #                  "display_options": {"show": {"operation": ["create"], 
                    #                          "resource": ["event"]}},
                    #                 "description":""}],
                    #     "default": "",
                    # },
                    # {
                    # "displayName": "Repeat How Many Times?", 
                    #  "name": "repeatHowManyTimes", 
                    #  "type": NodeParameterType.NUMBER, 
                    #  "description":"",
                    #  "display_options": {"show": {"operation": ["create"], 
                    #                          "resource": ["event"]}},
                    #  "typeOptions": {"minValue": 1}, 
                    #  "default": 1},
                    # {"displayName": "Repeat Until", 
                    #  "name": "repeatUntil", 
                    #  "description":"",
                    #  "type": NodeParameterType.DATETIME, 
                    #  "display_options": {"show": {"operation": ["create"], 
                    #                          "resource": ["event"]}},
                    #  "default": ""},
                    # {"displayName": "RRULE", 
                    #  "name": "rrule", 
                    #  "type": NodeParameterType.STRING, 
                    #  "display_options": {"show": {"operation": ["create"], 
                    #                          "resource": ["event"]}},
                    #  "default": "", 
                    #  "description": "Overrides repeat fields"},
                    {
                        "displayName": "Send Updates",
                        "name": "sendUpdates",
                        "type": NodeParameterType.OPTIONS,
                        "description":"",
                        "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                        "options": [
                            {"name":"All",
                             "value":"all",
                             "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                             "description":"Notify all guests"},
                            {"name":"External Only",
                             "value":"externalOnly",
                                "type": NodeParameterType.OPTIONS,
                             "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                             "description":"Notify non-Google guests only"},
                            {"name":"None",
                             "value":"none",
                            "type": NodeParameterType.OPTIONS,
                             "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                             "description":"No notifications (migration use)"},
                        ],
                        "default": "",
                        "type": NodeParameterType.OPTIONS,
                        "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                        "description": "Notifications behavior",
                    },
                    {
                        "displayName": "Show Me As",
                        "name": "showMeAs",
                        "type": NodeParameterType.OPTIONS,
                        "description":"",
                        "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                        "options": [
                            {"name":"Available",
                             "value":"transparent",
                            "type": NodeParameterType.OPTIONS,
                             "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                             "description":"Does not block time"},
                             
                            {"name":"Busy",     
                             "value":"opaque",  
                                "type": NodeParameterType.OPTIONS,
                             "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},   
                             "description":"Blocks time"},
                        ],
                        "default": "opaque",
                        "description": "Whether the event blocks time on the calendar",
                    },
                    {"displayName": "Summary", 
                     "name": "summary", 
                     "type": NodeParameterType.STRING, 
                     "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                     "default": "", 
                     "description": "Title"},
                    {
                        "displayName": "Visibility",
                        "name": "visibility",
                        "type": NodeParameterType.OPTIONS,
                        "description":"",
                        "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                        "options": [
                            {"name":"Confidential",
                             "value":"confidential",
                            "type": NodeParameterType.OPTIONS,
                             "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                             "description":"Private (compatibility)"},
                            {"name":"Default",     
                             "value":"default", 
                            "type": NodeParameterType.OPTIONS,   
                             "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}}, 
                             "description":"Calendar default"},
                            {"name":"Private",  
                            "type": NodeParameterType.OPTIONS,   
                             "value":"private",    
                             "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}}, 
                             "description":"Only attendees see details"},
                            {"name":"Public",      
                             "value":"public",     
                            "type": NodeParameterType.OPTIONS,
                             "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}}, 
                             "description":"Visible to all readers"},
                        ],
                        "default": "default",
                        "display_options": {"show": {"operation": ["create"], 
                                             "resource": ["event"]}},
                        "description": "Visibility of the event",
                    },
                ],
            },
            # {
            #     "display_name": "Reminders",
            #     "name": "remindersUi",
            #     "type": NodeParameterType.COLLECTION,
            #     "default": {},
            #     "description":"",
            #     "placeholder": "Add Reminder",
            #     "typeOptions": {"multipleValues": True},
            #     "display_options": {"show": {"resource": ["event"], 
            #                                  "operation": ["create"], 
            #                                  "useDefaultReminders": [False]}},
            #     "options": [
            #         {
            #             "name": "remindersValues",
            #             "displayName": "Reminder",
            #             "type": NodeParameterType.COLLECTION,
            #             "display_options": {"show": {"resource": ["event"], 
            #                                         "operation": ["create"], 
            #                                         "useDefaultReminders": [False]}},
                        
            #             "values": [
            #                 {"displayName": "Method", 
            #                  "name": "method", 
            #                  "type": NodeParameterType.OPTIONS, 
            #                  "description":"",

            #                 "display_options": {"show": {"resource": ["event"], 
            #                                                 "operation": ["create"], 
            #                                                 "useDefaultReminders": [False]}},
            #                  "options": [{"name":"Email",
                                          
            #                             "display_options": {"show": {"resource": ["event"], 
            #                                                         "operation": ["create"], 
            #                                                         "useDefaultReminders": [False]}},
            #                               "value":"email",
            #                               "description":""
            #                               },
            #                              {"name":"Popup",
            #                               "description":"",
            #                                 "display_options": {"show": {"resource": ["event"], 
            #                                                             "operation": ["create"], 
            #                                                             "useDefaultReminders": [False]}},
            #                               "value":"popup"}],
            #                                "default": ""},
            #                 {"displayName": "Minutes Before", 
            #                  "name": "minutes", 
            #                  "type": NodeParameterType.NUMBER, 
            #                  "description":"",

            #                 "display_options": {"show": {"resource": ["event"], 
            #                                             "operation": ["create"], 
            #                                             "useDefaultReminders": [False]}},
            #                  "typeOptions": {"minValue": 0, 
            #                                  "maxValue": 40320}, "default": 0},
            #             ],
            #         }
            #     ],
            #     "description": "Custom reminders when default reminders are disabled",
            # },

            # -------- event:delete --------
            {"display_name": "Event ID", 
             "name": "eventId", 
             "type": NodeParameterType.STRING, 
             "description":"",
             "required": True, 
             "default": "",
             "display_options": {"show": {"operation": ["delete"], 
                                          "resource": ["event"]}}},
            {
                "display_name": "Options",
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "description":"",
                "placeholder": "Add option",
                "default": {},
                "display_options": {"show": {"operation": ["delete"], 
                                             "resource": ["event"]}},
                "options": [
                    {
                        "displayName": "Send Updates",
                        "name": "sendUpdates",
                        "type": NodeParameterType.OPTIONS,
                        "description":"",
                         "display_options": {"show": {"operation": ["delete"], 
                                             "resource": ["event"]}},
                        
                        "options": [
                            {"name":"All",
                             "value":"all",
                                "type": NodeParameterType.OPTIONS,
                              "display_options": {"show": {"operation": ["delete"], 
                                             "resource": ["event"]}},
                             "description":"Notify all guests"},
                            {"name":"External Only",
                             "value":"externalOnly",
                        "type": NodeParameterType.OPTIONS,
                              "display_options": {"show": {"operation": ["delete"], 
                                             "resource": ["event"]}},
                             "description":"Notify non-Google guests only"},
                            {"name":"None",
                             "value":"none",
                        "type": NodeParameterType.OPTIONS,
                              "display_options": {"show": {"operation": ["delete"], 
                                             "resource": ["event"]}},
                             "description":"No notifications (migration use)"},
                        ],
                        "default": "",
                         "display_options": {"show": {"operation": ["delete"], 
                                             "resource": ["event"]}},
                        "description": "Notifications behavior",
                    },
                ],
            },

            # -------- event:get --------
            {"display_name": "Event ID", 
             "name": "eventId", 
             "type": NodeParameterType.STRING, 
             "required": True, 
             "default": "",
             "description":"",
             "display_options": {"show": {"operation": ["get"], 
                                          "resource": ["event"]}}},
            {
                "display_name": "Options",
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "description":"",
             "display_options": {"show": {"operation": ["get"], 
                                          "resource": ["event"]}},
                
                "placeholder": "Add option",
                "default": {},
                "display_options": 
                {
                    "show": {"operation": ["get"],
                              "resource": ["event"]}},
                    "description":"",
                    
                    "display_options": {"show": {"operation": ["get"], 
                                          "resource": ["event"]}},
                "options": [
                    {"displayName": "Max Attendees", 
                     "name": "maxAttendees", 
                     "type": NodeParameterType.NUMBER, 

                    "display_options": {"show": {"operation": ["get"], 
                                          "resource": ["event"]}},
                     "default": 0,
                     "description": "If exceeded, only the participant is returned"},
                    
                    {"name": "timezone", 
                     "type": NodeParameterType.OPTIONS, 
                     "description":"",
                     "display_options": {"show": {"operation": ["get"], 
                                          "resource": ["event"]}},
                     "display_name": "Timezone", 
                     "default": "UTC",
                     "options": [{"name": "UTC", 
                                  "value": "UTC",
                                  "description":"",
                                "type": NodeParameterType.OPTIONS,
                                  "display_options": {"show": {"operation": ["get"], 
                                          "resource": ["event"]}}}, 
                                 {"name": "Asia/Tehran", 
                                  "value": "Asia/Tehran",
                                  "description":"",
                                "type": NodeParameterType.OPTIONS,
                                  "display_options": {"show": {"operation": ["get"], 
                                          "resource": ["event"]}}}]},
                ],
            },

            # -------- event:getAll --------
            {
                "display_name": "Return All",
                "name": "returnAll",
                "type": NodeParameterType.BOOLEAN,
                "default": False,
                "description": "Whether to return all results or only up to a given limit",
                "display_options": {
                    "show": {"operation": ["getAll"], 
                             "resource": ["event"]}},
            },
            {
                "display_name": "Limit",
                "name": "limit",
                "type": NodeParameterType.NUMBER,
                "display_options": {
                    "show": {"operation": ["getAll"], 
                             "resource": ["event"]}},
                "typeOptions": {"minValue": 1,
                                 "maxValue": 500},
                "default": 50,
                "description": "Max number of results to return",
                "display_options": {"show": {"operation": ["getAll"], 
                                             "resource": ["event"], "returnAll": [False]}},
            },
            {
                "display_name": "After",
                "name": "timeMin",
                "type": NodeParameterType.DATETIME,
                "display_options": {
                    "show": {"operation": ["getAll"], 
                             "resource": ["event"]}},
                "default": "={{ $now }}",
                "description": "Events must be after this time (some part)",
                "display_options": {"show": {"operation": ["getAll"],
                                              "resource": ["event"]}},
            },
            {
                "display_name": "Before",
                "name": "timeMax",
                "type": NodeParameterType.DATETIME,
                "display_options": {
                    "show": {"operation": ["getAll"], 
                             "resource": ["event"]}},
                "default": "={{ $now.plus({ week: 1 }) }}",
                "description": "Events must be before this time (some part)",
                "display_options": {"show": {"operation": ["getAll"], 
                                             "resource": ["event"]}},
            },
            {
                "display_name": "Options",
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "description":"",
                "display_options": {
                    "show": {"operation": ["getAll"], 
                             "resource": ["event"]}},
                "placeholder": "Add option",
                "default": {},
                "display_options": {"show": {"operation": ["getAll"], 
                                             "resource": ["event"]}},
                "options": [
                    # (legacy <1.3 timeMin/timeMax)
                    {"displayName": "After",
                     "name":"timeMin",
                     "type":NodeParameterType.DATETIME,
                     "display_options": {
                    "show": {"operation": ["getAll"], 
                             "resource": ["event"]}},
                     "default":"","description":"Events must be after this time"},
                    {"displayName": "Before","name":"timeMax",
                     "type":NodeParameterType.DATETIME,
                     "display_options": {
                    "show": {"operation": ["getAll"], 
                             "resource": ["event"]}},
                     "default":"",
                     "description":"Events must be before this time"},

                    {"displayName":"Expand Events",
                     "name":"singleEvents",
                     "type":NodeParameterType.BOOLEAN,
                     "display_options": {
                    "show": {"operation": ["getAll"], 
                             "resource": ["event"]}},
                     "default":False,
                     "description":"Expand recurring events into instances"},

                    {"displayName":"Fields",
                     "name":"fields",
                     "type":NodeParameterType.STRING,
                     "display_options": {
                    "show": {"operation": ["getAll"], 
                             "resource": ["event"]}},
                     "placeholder":"e.g. items(ID,status,summary)",
                     "default":"",
                     "description":"Partial response fields. Use '*' for all (see Google performance docs)."},

                    {"displayName":"iCalUID",
                     "name":"iCalUID",
                     "type":NodeParameterType.STRING,
                     "display_options": {
                    "show": {"operation": ["getAll"], 
                             "resource": ["event"]}},
                     "default":"","description":"iCalendar format event ID to include"},
                    {"displayName":"Max Attendees",
                     "name":"maxAttendees",
                     "type":NodeParameterType.NUMBER,
                     "display_options": {
                    "show": {"operation": ["getAll"], 
                             "resource": ["event"]}},
                     "default":0,
                     "description":"If exceeded, only the participant is returned"},

                    {"displayName":"Order By",
                     "name":"orderBy",
                     "type":NodeParameterType.OPTIONS,
                     "display_options": {
                    "show": {"operation": ["getAll"], 
                             "resource": ["event"]}},
                     "options":[
                        {"name":"Start Time",
                         "value":"startTime",
                         "description":"Requires singleEvents=true"},
                        {"name":"Updated",   
                         "value":"updated",   
                         "description":"Order by last modification time"},
                    ],"default":"",
                    "description":"Sort order"},

                    {"displayName":"Query",
                     "name":"query",
                     "type":NodeParameterType.STRING,
                     "display_options": {
                            "show": {"operation": ["getAll"], 
                             "resource": ["event"]}},
                     "default":"",
                     "description":"Free text search across most fields (not extended properties)"},

                    # {"displayName":"Recurring Event Handling",
                    #  "name":"recurringEventHandling",
                    #  "type":NodeParameterType.OPTIONS,
                    #  "description":"",
                    #  "display_options": {
                    #         "show": {"operation": ["getAll"], 
                    #          "resource": ["event"]}},
                    #  "default":"expand",
                    #  "options":[
                    #     {"name":"All Occurrences",
                    #      "value":"expand",
                    #     "type": NodeParameterType.OPTIONS,
                    #      "display_options": {
                    #         "show": {"operation": ["getAll"], 
                    #          "resource": ["event"]}},
                    #      "description":"Return all instances in range"},
                    #     {"name":"First Occurrence",
                    #      "value":"first",
                    #     "type": NodeParameterType.OPTIONS,
                    #      "display_options": {
                    #         "show": {"operation": ["getAll"], 
                    #          "resource": ["event"]}},
                    #      "description":"Return the series master"},
                    #     {"name":"Next Occurrence", 
                    #      "value":"next", 
                    #     "type": NodeParameterType.OPTIONS,
                    #      "display_options": {
                    #         "show": {"operation": ["getAll"], 
                    #          "resource": ["event"]}},
                    #      "description":"Return next instance"},
                    #  ],
                    # },

                    {"displayName":"Show Deleted",
                     "name":"showDeleted",
                     "type":NodeParameterType.BOOLEAN,
                     "default":False,
                     "display_options": {
                            "show": {"operation": ["getAll"], 
                            "resource": ["event"]}},
                     "description":"Include cancelled events"},

                    {"displayName":"Show Hidden Invitations",
                     "name":"showHiddenInvitations",
                     "type":NodeParameterType.BOOLEAN,
                     "display_options": {
                    "show": {"operation": ["getAll"], 
                             "resource": ["event"]}},
                     "default":False,
                     "description":"Include hidden invitations"},

                    #  {"name": "timezone", 
                    #  "type": NodeParameterType.OPTIONS, 
                    #  "description":"",
                    #  "display_options": {
                    # "show": {"operation": ["getAll"], 
                    #          "resource": ["event"]}},
                    #  "display_name": "Timezone", 
                    #  "default": "UTC",
                    #  "options": [{"name": "UTC",
                    #                "value": "UTC",
                    #                 "type": NodeParameterType.OPTIONS,
                    #                "description":"",
                    #                "display_options": {
                    # "show": {"operation": ["getAll"], 
                    #          "resource": ["event"]}}}, 
                    #              {"name": "Asia/Tehran", 
                    #               "value": "Asia/Tehran",
                    #                 "type": NodeParameterType.OPTIONS,
                    #               "description":"",
                    #               "display_options": {
                    #             "show": {"operation": ["getAll"], 
                    #          "resource": ["event"]}},}]},
                    

                    {"displayName":"Updated Min",
                     "name":"updatedMin",
                     "type":NodeParameterType.DATETIME,
                     "default":"",
                     "display_options": {
                    "show": {"operation": ["getAll"], 
                             "resource": ["event"]}},
                     "description":"Lower bound for last modification (RFC3339). Deleted since then are included if showDeleted."}
                ],
            },

            # -------- event:update --------
            {"display_name": "Event ID", "name": "eventId", 
             "type": NodeParameterType.STRING, 
             "required": True, "default": "",
             "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}}},
            {
                "display_name": "Modify",
                "name": "modifyTarget",
                "type": NodeParameterType.OPTIONS,
                "description":"",

                "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                "options": [{
                    "name": "Recurring Event Instance", 
                             
                    "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                    "description":"",
                    "value": "instance"},
                      {
                    "name": "Recurring Event", 
                    "value": "event",
                    "description":"",
                    "type": NodeParameterType.OPTIONS,
                    "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}}}],
                "default": "instance",
                "display_options": {"show": {"operation": ["update"], 
                                             "resource": ["event"]}},

            },
            {
                "display_name": "Use Default Reminders",
                "name": "useDefaultReminders",
                "type": NodeParameterType.BOOLEAN,
                "description":"",
                "default": True,
                "display_options": {"show": {"operation": ["update"], 
                                             "resource": ["event"]}},
            },
            {
                "display_name": "Update Fields",
                "name": "updateFields",
                "type": NodeParameterType.COLLECTION,
                "description":"",
                "placeholder": "Add Field",
                "default": {},
                "display_options": {"show": {"operation": ["update"], 
                                             "resource": ["event"]}},
                "options": [
                    {"displayName":"All Day",
                     "name":"allday",
                     "type":NodeParameterType.BOOLEAN,
                     "description":"",
                        "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                     "default":True},
                    {
                        "displayName":"Attendees",
                        "name":"attendeesUi",
                        "type":NodeParameterType.COLLECTION,
                        "description":"",
                        "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                        "placeholder":"Add Attendees",
                        "default":{"values":{"mode":"add","attendees":[]}},
                        "options":[
                            {
                                "displayName":"Values",
                                "name":"values","values":[
                                    {"displayName":"Mode",
                                     "name":"mode",
                                     "type":NodeParameterType.OPTIONS,
                                     "description":"",
                                        "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                                     "default":"add",
                                     "options":[
                                        {"name":"Add Attendees Below [Default]",
                                         "value":"add",
                                        "type": NodeParameterType.OPTIONS,
                                         "description":"",
                                        "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}}
                                          },
                                        {"name":"Replace Attendees with Those Below",
                                         "value":"replace",
                                         "description":"",
                                        "type": NodeParameterType.OPTIONS,
                                        "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},},
                                    ]},
                                    {"displayName":"Attendees",
                                     "name":"attendees",
                                     "type":NodeParameterType.STRING,
                                     "description":"",
                                        "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                                     "typeOptions":
                                     {"multipleValues":True,
                                        "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                                      "multipleValueButtonText":"Add Attendee"},
                                      "default":"",
                                        "type": NodeParameterType.OPTIONS,
                                      "description":"Emails"}
                                ]
                            }
                        ],
                        "display_options": {
                            "show": {"operation": ["update"], 
                                     "resource": ["event"]}}
                    },
                    {
                        "displayName":"Attendees",
                        "name":"attendees",
                        "type":NodeParameterType.STRING,

                        "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                        "typeOptions":{"multipleValues":True,
                                       "multipleValueButtonText":"Add Attendee"},
                        "default":"",
                        "description":"(v1.0–1.1) Emails"
                       
                    },
                    {"displayName":"Description",
                     "name":"description",
                     "type":NodeParameterType.STRING,
                    "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                     "default":""},
                    {"displayName":"End",
                     "name":"end",
                     "type":NodeParameterType.DATETIME,
                    "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                     "default":"",
                     "description":"End time"},
                    {"displayName":"Guests Can Invite Others",
                     "name":"guestsCanInviteOthers",
                     "type":NodeParameterType.BOOLEAN,
                     "description":"",
                    "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                     "default":True},
                    {"displayName":"Guests Can Modify",
                     "name":"guestsCanModify",
                     "type":NodeParameterType.BOOLEAN,
                     "description":"",
                    "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                     "default":False},
                    {"displayName":"Guests Can See Other Guests",
                     "name":"guestsCanSeeOtherGuests",
                     "type":NodeParameterType.BOOLEAN,
                     "description":"",
                    "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                     "default":True},
                    {"displayName":"ID",
                     "name":"id",
                     "type":NodeParameterType.STRING,
                     "description":"",
                    "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                     "default":""},
                    {"displayName":"Location",
                     "name":"location",
                     "type":NodeParameterType.STRING,
                     "description":"",
                    "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                     "default":""},
                    {"displayName":"Max Attendees",
                     "name":"maxAttendees",
                     "type":NodeParameterType.NUMBER,
                     "description":"",
                    "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                     "default":0},
                    # {"displayName":"Repeat Frequency",
                    #  "name":"repeatFrecuency",
                    #  "type":NodeParameterType.OPTIONS,
                    #  "description":"",
                    # "display_options": {"show": {"operation": ["update"], 
                    #                       "resource": ["event"]}},
                    #  "options":[
                    #     {"name":"Daily",
                    #      "value":"Daily",
                    #     "type": NodeParameterType.OPTIONS,
                    #      "description":"",
                    #     "display_options": {"show": {"operation": ["update"], 
                    #                       "resource": ["event"]}},
                    #      },
                    #     {"name":"Weekly",
                    #      "value":"weekly",
                    #     "type": NodeParameterType.OPTIONS,
                    #      "description":"",
                    #     "display_options": {"show": {"operation": ["update"], 
                    #                       "resource": ["event"]}}},
                    #     {"name":"Monthly",
                    #      "value":"monthly",
                    #     "type": NodeParameterType.OPTIONS,
                    #      "description":"",
                    #      "display_options": {"show": {"operation": ["update"], 
                    #                       "resource": ["event"]}}},
                    #     {"name":"Yearly",
                    #      "value":"yearly",
                    #     "type": NodeParameterType.OPTIONS,
                    #      "description":"",
                    #      "display_options": {"show": {"operation": ["update"], 
                    #                       "resource": ["event"]}}}],
                    #     "default":"",
                    #     "display_options": {"show": {"operation": ["update"], 
                    #                       "resource": ["event"]}}},
                    # {"displayName":"Repeat How Many Times?",
                    #  "name":"repeatHowManyTimes",
                    #  "type":NodeParameterType.NUMBER,
                    #  "description":"",
                    #  "display_options": {"show": {"operation": ["update"], 
                    #                       "resource": ["event"]}},
                    #  "typeOptions":{"minValue":1},
                    #  "default":1},
                    # {"displayName":"Repeat Until",
                    #  "name":"repeatUntil",
                    #  "type":NodeParameterType.DATETIME,
                    #  "description":"",
                    #  "display_options": {"show": {"operation": ["update"], 
                    #                       "resource": ["event"]}},
                    #  "default":""},
                    # {"displayName":"RRULE",
                    #  "name":"rrule",
                    #  "type":NodeParameterType.STRING,
                    #  "display_options": {"show": {"operation": ["update"], 
                    #                       "resource": ["event"]}},
                    #  "default":""},
                    {
                        "displayName":"Send Updates",
                        "name":"sendUpdates",
                        "type":NodeParameterType.OPTIONS,
                        "description":"",
                        "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                        "options":[
                            {"name":"All",
                             "value":"all",
                             "description":"",
                            "type": NodeParameterType.OPTIONS,
                            "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}}},
                            {"name":"External Only",
                             "value":"externalOnly",
                             "description":"",
                            "type": NodeParameterType.OPTIONS,
                            "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},},
                            {"name":"None",
                             "value":"none",
                             "description":"",
                            "type": NodeParameterType.OPTIONS,
                            "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}}}],
                        "default":"",
                          "description":"Notifications behavior"
                    },
                    {"displayName":"Show Me As",
                     "name":"showMeAs",
                     "type":NodeParameterType.OPTIONS,
                     "description":"",
                     "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                     "options":[
                        {"name":"Available",
                         "value":"transparent",
                         "description":"",
                            "type": NodeParameterType.OPTIONS,
                         "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}}},
                         {"name":"Busy",
                          "value":"opaque",
                          "description":"",
                            "type": NodeParameterType.OPTIONS,
                          "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}}}],
                         "default":"opaque"
                                          },
                    {"displayName":"Start",
                     "name":"start",
                     "type":NodeParameterType.DATETIME,
                     "default":"",
                     "description":"Start time",
                     "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}}},
                    {"displayName":"Summary",
                     "name":"summary",
                     "type":NodeParameterType.STRING,
                     "description":"",
                     "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                     "default":""},
                    {"displayName":"Visibility",
                     "name":"visibility",
                     "type":NodeParameterType.OPTIONS,
                     "description":"",
                     "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}},
                     "options":[
                        {"name":"Confidential",
                         "value":"confidential",
                         "description":"",
                        "type": NodeParameterType.OPTIONS,
                         "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}}},
                         {"name":"Default",
                          "value":"default",
                          "description":"",
                        "type": NodeParameterType.OPTIONS,
                          "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}}},
                        {"name":"Private",
                         "value":"private",
                         "description":"",
                        "type": NodeParameterType.OPTIONS,
                         "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}}},
                        {"name":"Public",
                         "value":"public",
                         "description":"",
                        "type": NodeParameterType.OPTIONS,
                         "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}}}],
                        "default":"default",
                        "description":"",
                        "display_options": {"show": {"operation": ["update"], 
                                          "resource": ["event"]}}},
                ],
            },
            {
                "display_name": "Reminders",
                "name": "remindersUi",
                "type": NodeParameterType.COLLECTION,
                "default": {},
                "placeholder": "Add Reminder",
                "typeOptions": {"multipleValues": True},
                "display_options": {"show": {"resource": ["event"], 
                                             "operation": ["update"], 
                                             "useDefaultReminders": [False]}},
                "options": [
                    {
                        "name": "remindersValues",
                        "displayName": "Reminder",
                        "description":"",
                        "values": [
                            {"displayName": "Method", 
                             "name": "method", 
                             "type": NodeParameterType.OPTIONS, 
                             "description":"",

                             "display_options": {"show": {"resource": ["event"], 
                                             "operation": ["update"], 
                                             "useDefaultReminders": [False]}},
                             "options": 
                             [{"name":"Email",
                               "value":"email",
                               "description":"",
                                "type": NodeParameterType.OPTIONS,
                               "display_options": {"show": {"resource": ["event"], 
                                             "operation": ["update"], 
                                             "useDefaultReminders": [False]}}},
                               {"name":"Popup",
                                "value":"popup",
                                "description":"",
                                "type": NodeParameterType.OPTIONS,
                                "display_options": {"show": {"resource": ["event"], 
                                             "operation": ["update"], 
                                             "useDefaultReminders": [False]}}}] 
                               , "default": ""},
                            {"displayName": "Minutes Before", 
                             "name": "minutes", 
                             "type": NodeParameterType.NUMBER, 
                             "description":"",
                             "display_options": {"show": {"resource": ["event"], 
                                             "operation": ["update"], 
                                             "useDefaultReminders": [False]}},
                             "typeOptions": {"minValue": 0, "maxValue": 40320}, 
                             "default": 0},
                        ],
                    }
                ],
                "description": "Custom reminders when default reminders are disabled",
            },
    ],

        "credentials": [{"name": "googleCalendarApi", "required": True}],
    }
    icon = "googleCalendar.svg"
    color = "#4285f4"
    _base_url = "https://www.googleapis.com/calendar/v3"

    # ======================= OAuth & Credentials =======================
    @staticmethod
    def has_access_token(credentials_data: Dict[str, Any]) -> bool:
        """Check if credentials have access token (n8n's approach)"""
        # Handle nested structure from credential system
        if 'data' in credentials_data:
            credentials_data = credentials_data['data']
        
        oauth_token_data = credentials_data.get('oauthTokenData')
        if not isinstance(oauth_token_data, dict):
            return False
        return 'access_token' in oauth_token_data

    def get_credential_type(self):
        return self.properties["credentials"][0]['name']

    def _is_token_expired(self, oauth_data: Dict[str, Any]) -> bool:
        """Check if the current token is expired"""
        if "expires_at" not in oauth_data:
            return False
        # Add 30 second buffer
        return time.time() > (oauth_data["expires_at"] - 30)
    
    def refresh_token(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Refresh OAuth2 access token with proper invalid_grant handling"""
            
        if not data.get("oauthTokenData") or not data["oauthTokenData"].get("refresh_token"):
            raise ValueError("No refresh token available")

        oauth_data = data["oauthTokenData"]

        token_data = {
            "grant_type": "refresh_token",
            "refresh_token": oauth_data["refresh_token"],
        }
        
        headers = {}

        # Add client credentials based on authentication method
        if data.get("authentication", "header") == "header":
            auth_header = base64.b64encode(
                f"{data['clientId']}:{data['clientSecret']}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {auth_header}"
        else:
            token_data.update({
                "client_id": data["clientId"],
                "client_secret": data["clientSecret"]
            })
        
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        
        try:
            response = requests.post(
                data["accessTokenUrl"],
                data=urlencode(token_data),
                headers=headers,
            )
            
            if response.status_code == 200:
                new_token_data = response.json()
                
                # Update token data (preserve existing data)
                updated_oauth_data = oauth_data.copy()
                updated_oauth_data["access_token"] = new_token_data["access_token"]
                
                if "expires_in" in new_token_data:
                    updated_oauth_data["expires_at"] = time.time() + new_token_data["expires_in"]
                
                # Only update refresh token if a new one is provided
                if "refresh_token" in new_token_data:
                    updated_oauth_data["refresh_token"] = new_token_data["refresh_token"]
                
                # Preserve any additional token data
                for key, value in new_token_data.items():
                    if key not in ["access_token", "expires_in", "refresh_token"]:
                        updated_oauth_data[key] = value
                
                # Save updated token data
                data["oauthTokenData"] = updated_oauth_data
                    
                self.update_credentials(self.get_credential_type(), data)
                return data
            else:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    error_data = {"error": response.text}
                
                error_code = error_data.get("error", "")
                # Handle invalid_grant - user needs to reconnect
                if error_code == "invalid_grant":
                    raise ValueError(f"OAuth token invalid (invalid_grant). User must reconnect their Google Calendar account.")
                
                raise Exception(f"Token refresh failed with status {response.status_code}: {error_data.get('error', 'Unknown error')}")
                
        except requests.RequestException as e:
            raise Exception(f"Token refresh request failed: {str(e)}")
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Token refresh failed: {str(e)}")

    def _get_access_token(self) -> str:
        """Get a valid access token for Google Calendar API from the credentials"""
        try:
            credentials = self.get_credentials("googleCalendarApi")
            if not credentials:
                raise ValueError("Google Calendar API credentials not found")

            if not self.has_access_token(credentials):
                raise ValueError("Google Calendar API access token not found")

            oauth_token_data = credentials.get('oauthTokenData', {})
            if self._is_token_expired(oauth_token_data):
                credentials = self.refresh_token(credentials)

            return credentials['oauthTokenData']['access_token']
            
        except Exception as e:
            logger.error(f"Error getting Google Calendar access token: {str(e)}")
            raise ValueError(f"Failed to get Google Calendar access token: {str(e)}")

    # ======================= Execution =======================
    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Google Calendar operations."""
        try:
            input_data = self.get_input_data()
            if not input_data:
                return [[]]

            result_items = []

            for i, item in enumerate(input_data):
                try:
                    if hasattr(item, "json_data"):
                        _ = item.json_data or {}

                    resource = self.get_node_parameter("resource", i, "event")
                    operation = self.get_node_parameter("operation", i, "getAll")
                    continue_on_fail = self.get_node_parameter("continueOnFail", i, False)

                    result = None
                    if resource == "calendar":
                        if operation == "availability":
                            result = self._calendar_availability(i)
                        else:
                            raise ValueError(f"Unsupported operation '{operation}' for resource 'calendar'")
                    elif resource == "event":
                        if operation == "getAll":
                            result = self._get_events()
                        elif operation == "create":
                            result = self._create_event(i)
                        elif operation == "get":
                            result = self._get_event_id(i)
                        elif operation == "update":
                            result = self._update_event(i)
                        elif operation == "delete":
                            result = self._delete_event(i)
                        else:
                            raise ValueError(f"Unsupported operation '{operation}' for resource 'event'")
                    else:
                        raise ValueError(f"Unsupported resource '{resource}'")

                    # Ensure NodeExecutionData objects
                    
                    # Add result to items
                    if isinstance(result, list):
                        for res_item in result:
                            result_items.append(NodeExecutionData(
                                json_data=res_item,
                                binary_data=None
                            ))
                    else:
                        result_items.append(NodeExecutionData(
                            json_data=result,
                            binary_data=None
                        ))
                
                    # result_items.extend(_wrap_result(result))

                except Exception as e:
                    logger.error(f"Google Calendars Node - Error processing item {i}: {str(e)}", exc_info=True)
                    error_item = NodeExecutionData(
                        json_data={
                            "error": str(e),
                            "resource": self.get_node_parameter("resource", i, "event"),
                            "operation": self.get_node_parameter("operation", i, "getAll"),
                            "item_index": i,
                        },
                        binary_data=None,
                    )
                    result_items.append(error_item)
                    if not continue_on_fail:
                        break

            return [result_items]

        except Exception as e:
            logger.error(f"Google Calendars Node - Execute error: {str(e)}", 
                         exc_info=True)
            return [[NodeExecutionData(json_data={"error": f"Error in Google Calendars node: {str(e)}"}, binary_data=None)]]


    def google_api_request(self, method: str, url: str, body: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
        access_token = self._get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        try:
            if method == 'GET':
                response = requests.get(url, params=params, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, params=params, json=body, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, params=params, headers=headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, params=params, json=body, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return {} if response.status_code == 204 else response.json()

        except requests.RequestException as e:
            msg = str(e)
            try:
                if getattr(e, "response", None) is not None:
                    jd = e.response.json()
                    msg = f"Google API Error: {jd.get('error', {}).get('message', 'Unknown error')}"
                    if e.response.status_code == 401:
                        # point to the correct credentials
                        creds = self.get_credentials("googleCalendarApi")
                        if isinstance(creds, dict):
                            # n8n-like shape: keep fields consistent; do not self-nest
                            if 'oauthTokenData' in creds:
                                creds['oauthTokenData']['access_token'] = None
                                creds['oauthTokenData']['expires_at'] = 0
                        msg += " - Token invalid/expired."
            except Exception:
                pass
            logger.error(f"Google API request failed: {msg}")
            raise ValueError(msg)
    
    # ======================= Event Operations =======================
    def _get_events(self) -> List[Dict[str, Any]]:
        """List events from Google Calendar (getAll) and return a plain list of event dicts."""
        try:
            # Calendar
            calendar_param = self.get_node_parameter("calendar", 0, {})
            calendar_id = googleCalendar_norm._resolve_calendar_id(calendar_param)

            # Controls
            return_all = bool(self.get_node_parameter("returnAll", 0, False))
            limit_param = None if return_all else int(self.get_node_parameter("limit", 0, 50))

            # Time window (top-level)
            time_min = self.get_node_parameter("timeMin", 0, "") or ""
            time_max = self.get_node_parameter("timeMax", 0, "") or ""

            # Options
            opts = self.get_node_parameter("options", 0, {}) or {}
            single_events = bool(opts.get("singleEvents", False))
            ical_uid = (opts.get("iCalUID") or "").strip()
            max_attendees = int(opts.get("maxAttendees") or 0)
            order_by = (opts.get("orderBy") or "").strip()          # startTime | updated
            query_text = (opts.get("query") or "").strip()
            # recurring_handling = (opts.get("recurringEventHandling") or "expand").strip()  # expand|first|next
            show_deleted = bool(opts.get("showDeleted", False))
            show_hidden_inv = bool(opts.get("showHiddenInvitations", False))
            # tz_opt = (opts.get("timezone") or "").strip()
            updated_min = (opts.get("updatedMin") or "").strip()
            # not sure what this does?
            # if recurring_handling == "expand" or not recurring_handling:
            #     single_events = True

            # Build params
            params: Dict[str, Any] = {}
            if time_min:
                params["timeMin"] = time_min
            if time_max:
                params["timeMax"] = time_max
            if single_events:
                params["singleEvents"] = True
            # if order_by in ("startTime", "updated"):
            #     params["orderBy"] = order_by
            if query_text:
                params["q"] = query_text
            if show_hidden_inv:
                params["showHiddenInvitations"] = True
            # if tz_opt:
            #     params["timeZone"] = tz_opt
            if updated_min:
                params["updatedMin"] = updated_min
            if ical_uid:
                params["iCalUID"] = ical_uid
            if max_attendees > 0:
                params["maxAttendees"] = max_attendees
            params["maxResults"] = 250 if return_all else min(max(1, limit_param or 50), 250)

            # Partial response
            params["fields"] = (
                "nextPageToken,items("
                "id,summary,description,htmlLink,hangoutLink,location,status,visibility,"
                "start(date,dateTime,timeZone),end(date,dateTime,timeZone),"
                "organizer(email),attendees(email,responseStatus,displayName),"
                "recurrence,recurringEventId,transparency,created,updated)"
            )

            url = f"{self._base_url}/calendars/{calendar_id}/events"

            items: List[Dict[str, Any]] = []
            page_token: Optional[str] = None

            while True:
                page_params = dict(params)
                if page_token:
                    page_params["pageToken"] = page_token

                data = self.google_api_request("GET", url, params=page_params)
                page_items = (data.get("items") or [])

                # Drop cancelled unless explicitly requested
                if not show_deleted:
                    page_items = [it for it in page_items if it.get("status") != "cancelled"]

                # Timezone conversion (timed events only)
                # if tz_opt:
                #     for it in page_items:
                #         st = it.get("start") or {}
                #         en = it.get("end") or {}
                #         if "dateTime" in st and st["dateTime"]:
                #             st["dateTime"] = googleCalendar_norm.timezone_convert(st["dateTime"], tz_opt)
                #             st["timeZone"] = tz_opt
                #         if "dateTime" in en and en["dateTime"]:
                #             en["dateTime"] = googleCalendar_norm.timezone_convert(en["dateTime"], tz_opt)
                #             en["timeZone"] = tz_opt

                items.extend(page_items)

                # Stop if limited
                if not return_all and len(items) >= (limit_param or 50):
                    items = items[: (limit_param or 50)]
                    break

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

            # Recurring handling post-processing like n8n
            # if recurring_handling == "next":
            #     updated: List[Dict[str, Any]] = []
            #     for ev in items:
            #         if ev.get("recurrence"):
            #             inst = googleCalendar_norm._maybe_replace_with_next_instance(calendar_id, ev.get("id"), tz_opt)
            #             updated.append(inst or ev)
            #         else:
            #             updated.append(ev)
            #     items = updated
            # elif recurring_handling == "first":
            #     # Keep only series masters whose created falls inside [timeMin, timeMax] if both are set;
            #     # emulate n8n’s filter (applies only to recurring events)
            #     items = [ev for ev in items if googleCalendar_norm.inside_window(ev,time_min,time_max)]

            return items

        except Exception as e:
            logger.error(f"Error getting events from Google Calendar: {str(e)}", exc_info=True)
            raise

    def _get_event_id(self, item_index: int) -> Dict[str, Any]:
        """Get a Google Calendar event by ID"""
        try:
            access_token = self._get_access_token()

            # ---- Required: eventId ----
            event_id = self.get_node_parameter("eventId", item_index, "")
            if not event_id:
                raise ValueError("event ID is required for get operation")

            # ---- Calendar selection (same shape as create) ----
            calendar_param = self.get_node_parameter("calendar", 0, {})
            calendar_id=googleCalendar_norm._resolve_calendar_id(calendar_param)
           

            # ---- Options collection from UI ----
            # UI: { name: "options", options: [{ name: "maxAttendees" }, { name: "timezone" }] }
            options = self.get_node_parameter("options", item_index, {}) or {}
            max_attendees = options.get("maxAttendees", 0)
            # timezone_opt  = options.get("timezone", "Asia/Tehran")  # e.g. "UTC" | "Asia/Tehran"
            # return_next_instance = options.get("returnNextInstance", False)


            # ---- Build query params for events.get ----
            # https://developers.google.com/calendar/api/v3/reference/events/get
            params: Dict[str, Any] = {}

            if int(max_attendees) > 0:
                params["maxAttendees"] = max_attendees

            # if timezone_opt.strip():
            #     params["timezone"] = timezone_opt.strip()

            

            # Partial response to keep payload small
            params["fields"] = (
                "id,summary,description,htmlLink,hangoutLink,location,status,visibility,"
                "start,end,created,updated,organizer,"
                "attendees(email,responseStatus,displayName),"
                "recurrence,recurringEventId,transparency"
            )

            # ---- Request ----
            url = f"{self._base_url}/calendars/{calendar_id}/events/{event_id}"
            headers = {"Authorization": f"Bearer {access_token}"}

            resp = requests.get(url, headers=headers, params=params, timeout=30)
            if resp.status_code == 200:
                event_data = resp.json()

                attendees = event_data.get("attendees") or []
                if isinstance(attendees, list) and attendees:
                    applied_max = int(params.get("maxAttendees") or 0)
                    event_data["attendees"] = attendees[:applied_max] if applied_max > 0 else attendees
                return event_data

            raise ValueError(f"Get event API failed ({resp.status_code}): {resp.text}")

        except Exception as e:
            logger.error(f"Error getting Google Calendar event: {e}", exc_info=True)
            raise
    def _create_event(self, item_index: int):
        """Create a new Google Calendar event"""

        try:
            access_token = self._get_access_token()

            # ---------- Common: calendar ----------
            calendar_param = self.get_node_parameter("calendar", 0, {})
            if not calendar_param:
                raise ValueError("Calendar parameter not provided")
            calendar_id=googleCalendar_norm._resolve_calendar_id(calendar_param)
           

            # ---------- Required times ----------
            start_raw = self.get_node_parameter("start", item_index, "")
            end_raw   = self.get_node_parameter("end",   item_index, "")
            if not start_raw or not end_raw:
                raise ValueError("Start and End are required")

            # ---------- Collections / toggles ----------
            # use_default_reminders = self.get_node_parameter("useDefaultReminders", item_index, True)
            additional = self.get_node_parameter("additionalFields", item_index, {}) or {}
           
            # ---------- Title / meta ----------
            summary     = additional.get("summary", "")
            description = additional.get("description", "")
            location    = additional.get("location", "")
            visibility  = additional.get("visibility", "default")  # default|public|private|confidential
            show_me_as  = additional.get("showMeAs", "opaque")     # opaque|transparent -> maps to 'transparency'
            guests_invite = additional.get("guestsCanInviteOthers", True)
            guests_modify = additional.get("guestsCanModify", False)
            guests_see    = additional.get("guestsCanSeeOtherGuests", True)
            

            # ---------- Timezone ----------
            # If you add an event-level timezone control in UI, read it here. Otherwise default.
            # time_zone = additional.get("timeZone") or "UTC"
            
            # all_day = additional.get("allday", False)
            start_obj, end_obj = {"dateTime": str(start_raw)}, {"dateTime": str(end_raw)}
            #  googleCalendar_norm._build_start_end(start_raw, end_raw, time_zone, all_day)

            attendees_list = googleCalendar_norm._build_attendees(additional)
            
            # reminders = googleCalendar_norm._build_reminders(use_default_reminders, additional)

            # recurrence = googleCalendar_norm._build_recurrence(additional)

            # ---------- Build body ----------
            event_data = {
                "summary": summary or None,
                "description": description or None,
                "location": location or None,
                "start": start_obj,
                "end": end_obj,
                "visibility": visibility,
                "transparency": show_me_as,
                "guestsCanInviteOthers": guests_invite,
                "guestsCanModify": guests_modify,
                "guestsCanSeeOtherGuests": guests_see,
                "attendees": attendees_list or None,
                # "reminders": reminders,
            }
            # if recurrence:
            #     event_data["recurrence"] = recurrence

            # Prune Nones to keep payload tidy
            event_data = {k: v for k, v in event_data.items() if v is not None}

            # ---------- Query params ----------
            # sendUpdates and maxAttendees belong to query, not body
            send_updates = additional.get("sendUpdates", "") or "none"  # all|externalOnly|none
            max_attendees = additional.get("maxAttendees", 0)
            params = {}
            if send_updates in ("all", "externalOnly", "none"):
                params["sendUpdates"] = send_updates
            if max_attendees > 0:
                params["maxAttendees"] = int(max_attendees)

            # ---------- Request ----------
            url = f"{self._base_url}/calendars/{calendar_id}/events"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            
            resp = requests.post(url, headers=headers, params=params, json=event_data, timeout=30)
            if resp.status_code in (200, 201):
                return resp.json()
            raise ValueError(f"Create event API failed ({resp.status_code}): {resp.text}")

        except Exception as e:
            logger.error(f"Error creating Google Calendar event: {e}", exc_info=True)
            raise

    def _create_event1(self, item_index: int):
        """Create a new Google Calendar event"""

        try:
            access_token = self._get_access_token()

            # ---------- Common: calendar ----------
            calendar_param = self.get_node_parameter("calendar", 0, {})
            if not calendar_param:
                raise ValueError("Calendar parameter not provided")
            calendar_id=googleCalendar_norm._resolve_calendar_id(calendar_param)
           

            # ---------- Required times ----------
            start_raw = self.get_node_parameter("start", item_index, "")
            end_raw   = self.get_node_parameter("end",   item_index, "")
            if not start_raw or not end_raw:
                raise ValueError("Start and End are required")

            # ---------- Collections / toggles ----------
            # use_default_reminders = self.get_node_parameter("useDefaultReminders", item_index, True)
            additional = self.get_node_parameter("additionalFields", item_index, {}) or {}
           
            # ---------- Title / meta ----------
            summary     = additional.get("summary", "")
            description = additional.get("description", "")
            location    = additional.get("location", "")
            visibility  = additional.get("visibility", "default")  # default|public|private|confidential
            show_me_as  = additional.get("showMeAs", "opaque")     # opaque|transparent -> maps to 'transparency'
            guests_invite = additional.get("guestsCanInviteOthers", True)
            guests_modify = additional.get("guestsCanModify", False)
            guests_see    = additional.get("guestsCanSeeOtherGuests", True)

            # ---------- Timezone ----------
            # If you add an event-level timezone control in UI, read it here. Otherwise default.
            # time_zone = additional.get("timeZone") or "UTC"
            
            # all_day = additional.get("allday", False)
            start_obj, end_obj = {"dateTime": str(start_raw)}, {"dateTime": str(end_raw)}
            #  googleCalendar_norm._build_start_end(start_raw, end_raw, time_zone, all_day)

            attendees_list = googleCalendar_norm._build_attendees(additional)
            
            # reminders = googleCalendar_norm._build_reminders(use_default_reminders, additional)

            # recurrence = googleCalendar_norm._build_recurrence(additional)

            # ---------- Build body ----------
            event_data = {
                "summary": summary or None,
                "description": description or None,
                "location": location or None,
                "start": start_obj,
                "end": end_obj,
                "visibility": visibility,
                "transparency": show_me_as,
                "guestsCanInviteOthers": guests_invite,
                "guestsCanModify": guests_modify,
                "guestsCanSeeOtherGuests": guests_see,
                "attendees": attendees_list or None,
                # "reminders": reminders,
            }
            # if recurrence:
            #     event_data["recurrence"] = recurrence

            # Prune Nones to keep payload tidy
            event_data = {k: v for k, v in event_data.items() if v is not None}

            # ---------- Query params ----------
            # sendUpdates and maxAttendees belong to query, not body
            send_updates = additional.get("sendUpdates", "") or "none"  # all|externalOnly|none
            max_attendees = additional.get("maxAttendees", 0)
            params = {}
            if send_updates in ("all", "externalOnly", "none"):
                params["sendUpdates"] = send_updates
            if max_attendees > 0:
                params["maxAttendees"] = int(max_attendees)

            # ---------- Request ----------
            url = f"{self._base_url}/calendars/{calendar_id}/events"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            
            resp = requests.post(url, headers=headers, params=params, json=event_data, timeout=30)
            if resp.status_code in (200, 201):
                return resp.json()
            raise ValueError(f"Create event API failed ({resp.status_code}): {resp.text}")

        except Exception as e:
            logger.error(f"Error creating Google Calendar event: {e}", exc_info=True)
            raise
    def _update_event(self, item_index: int) -> Dict[str, Any]:
        """Update an existing Google Calendar event and return the final event object from Google."""

        access_token = self._get_access_token()

        # ---- Required ----
        event_id = self.get_node_parameter("eventId", item_index, "")
        if not event_id:
            raise ValueError("Event ID is required for update operation")

        # ---- Calendar ----
        calendar_param = self.get_node_parameter("calendar", 0, {})
        if not calendar_param:
            raise ValueError("Calendar parameter not provided")
        calendar_id = googleCalendar_norm._resolve_calendar_id(calendar_param)

        # ---- UI fields ----
        use_default_reminders = self.get_node_parameter("useDefaultReminders", item_index, True)
        uf = self.get_node_parameter("updateFields", item_index, {}) or {}

        summary     = uf.get("summary", "")
        description = uf.get("description", "")
        location    = uf.get("location", "")
        visibility  = uf.get("visibility", "")        # default|public|private|confidential
        show_me_as  = uf.get("showMeAs", "")          # opaque|transparent
        guests_inv  = uf.get("guestsCanInviteOthers", None)
        guests_mod  = uf.get("guestsCanModify", None)
        guests_see  = uf.get("guestsCanSeeOtherGuests", None)

        # all_day  = uf.get("allday", False)
        start_in = uf.get("start", "")
        end_in   = uf.get("end", "")
        if (start_in and not end_in) or (end_in and not start_in):
            raise ValueError("When updating time, both Start and End must be provided")

        start_obj = end_obj = None
        # if start_in and end_in:
        #     start_obj, end_obj = googleCalendar_norm._build_start_end(
        #         start_in, end_in, googleCalendar_norm.time_zone, all_day
        #     )

        # recurrence = googleCalendar_norm._build_recurrence(uf)

        # ---- Query params (not body) ----
        send_updates = uf.get("sendUpdates", "") or ""
        max_attendees = uf.get("maxAttendees", 0)
        params = {}
        if send_updates in ("all", "externalOnly", "none"):
            params["sendUpdates"] = send_updates
        if int(max_attendees) > 0:
            params["maxAttendees"] = int(max_attendees)

        # ---- Build minimal PATCH body (only provided fields) ----
        event_data: Dict[str, Any] = {}

        if summary:
            event_data["summary"] = summary
        if description:
            event_data["description"] = description
        if location:
            event_data["location"] = location
        if visibility:
            event_data["visibility"] = visibility
        if show_me_as:
            event_data["transparency"] = show_me_as

        if guests_inv is not None:
            event_data["guestsCanInviteOthers"] = (guests_inv)
        if guests_mod is not None:
            event_data["guestsCanModify"] = (guests_mod)
        if guests_see is not None:
            event_data["guestsCanSeeOtherGuests"] = (guests_see)

        if start_obj and end_obj:
            event_data["start"] = start_obj
            event_data["end"] = end_obj

        # if recurrence is not None:
        #     event_data["recurrence"] = recurrence

        # Reminders (keep your toggle behavior; if you only want to change when explicitly set, guard it)
        event_data["reminders"] = {"useDefault": (use_default_reminders)}

        # ---- Attendees (UI + legacy) ----
        attendees_ui = uf.get("attendeesUi", {}) or {}
        attendees_list: list = []
        mode = "replace"

        if "values" in attendees_ui and attendees_ui["values"]:
            vals = attendees_ui["values"] or {}
            mode = (vals.get("mode") or "add").strip() or "add"
            for a in (vals.get("attendees") or []):
                if a.strip():
                    attendees_list.append({"email": a.strip()})

        legacy_att = uf.get("attendees", "")
        #fix
        if legacy_att and not attendees_list:
            parts = [p.strip() for p in re.split(r"[,\s;]+", str(legacy_att)) if p.strip()]
            attendees_list = [{"email": e} for e in parts]
            mode = "replace"

        if attendees_list:
            # Fetch current attendees only if needed to support "add"
            current_att = []
            if mode == "add":
                get_url = f"{self._base_url}/calendars/{calendar_id}/events/{event_id}"
                headers = {"Authorization": f"Bearer {access_token}"}
                get_params = {"fields": "attendees(email)", "maxAttendees": params.get("maxAttendees", 250)}
                cur = requests.get(get_url, headers=headers, params=get_params, timeout=30)
                if cur.status_code == 200:
                    current_att = cur.json().get("attendees") or []

            final_attendees = googleCalendar_norm._compute_attendees_patch(attendees_list, mode, current_att)
            if final_attendees is not None:
                event_data["attendees"] = final_attendees

        # ---- PATCH and return Google's full event ----
        url = f"{self._base_url}/calendars/{calendar_id}/events/{event_id}"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        resp = requests.patch(url, headers=headers, params=params, json=event_data, timeout=30)
        if resp.status_code not in (200, 201):
            raise ValueError(f"Update event API failed ({resp.status_code}): {resp.text}")

        # IMPORTANT: return the provider's full, final event (unchanged + changed fields)
        return resp.json()
    # ...existing code...
    def _delete_event(self, item_index: int) -> Dict[str, Any]:
        """Delete a Google Calendar event"""
        try:
            access_token = self._get_access_token()

            # Get event ID
            event_id = self.get_node_parameter("eventId", item_index, "")
            if not event_id:
                raise ValueError("Event ID is required for deleting an event")

            calendar_param = self.get_node_parameter("calendar", 0, {})
            if not calendar_param:
                raise ValueError("Calendar parameter not provided")
            calendar_id=googleCalendar_norm._resolve_calendar_id(calendar_param)
           
            # Optional delete options (sendUpdates)
            opts = self.get_node_parameter("options", item_index, {}) or {}
            params = {}
            su = (opts.get("sendUpdates") or "").strip()
            if su in ("all", "externalOnly", "none"):
                params["sendUpdates"] = su

            # Delete event
            delete_url = f"{self._base_url}/calendars/{calendar_id}/events/{event_id}"
            response = requests.delete(
                delete_url,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30,
            )

            if response.status_code == 204:
                return {"id": event_id, "status": "Event deleted"}
            else:
                # If already deleted, treat as idempotent success
                try:
                    err = response.json()
                    code = err.get("error", {}).get("code")
                    reason = (err.get("error", {}).get("errors") or [{}])[0].get("reason")
                    if code == 410 and reason == "deleted":
                        return {"id": event_id, "status": "Already deleted"}
                except Exception:
                    pass
                error_text = response.text
                raise ValueError(f"Delete event API failed: {error_text}")
        except Exception as e:
            logger.error(f"Error deleting Google Calendar event: {str(e)}", exc_info=True)
            raise
# ...existing code...
    # def _delete_event(self, item_index: int) -> Dict[str, Any]:
        # """Delete a Google Calendar event"""
        # try:
        #     access_token = self._get_access_token()

        #     # Get event ID
        #     event_id = self.get_node_parameter("eventId", item_index, "")
        #     if not event_id:
        #         raise ValueError("Event ID is required for deleting an event")

        #     calendar_param = self.get_node_parameter("calendar", 0, {})
        #     if not calendar_param:
        #         raise ValueError("Calendar parameter not provided")
        #     calendar_id=googleCalendar_norm._resolve_calendar_id(calendar_param)
           
            
             # Optional delete options (sendUpdates)
#              opts = self.get_node_parameter("options", item_index, {}) or {}
#              params = {}
#              su = (opts.get("sendUpdates") or "").strip()
#              if su in ("all", "externalOnly", "none"):
#                  params["sendUpdates"] = su
 
#             # Delete event
#             delete_url = f"{self._base_url}/calendars/{calendar_id}/events/{event_id}"
# -            response = requests.delete(delete_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=30)
#              response = requests.delete(
#                  delete_url,
#                  params=params,
#                  headers={"Authorization": f"Bearer {access_token}"},
#                  timeout=30,
#              )

#             if response.status_code == 204:
#                 return {"id": event_id, "status": "Event deleted"}
# -            else:
# -                error_text = response.text
# -                raise ValueError(f"Delete event API failed: {error_text}")
#              else:
#                  # If already deleted, treat as idempotent success
#                  try:
#                      err = response.json()
#                      code = err.get("error", {}).get("code")
#                      reason = (err.get("error", {}).get("errors") or [{}])[0].get("reason")
#                      if code == 410 and reason == "deleted":
#                          return {"id": event_id, "status": "Already deleted"}
#                  except Exception:
#                      pass
#                  error_text = response.text
#                  raise ValueError(f"Delete event API failed: {error_text}")
#         except Exception as e:
#             logger.error(f"Error deleting Google Calendar event: {str(e)}", exc_info=True)
#             raise
# ...existing code...

    # ======================= Calendar Operations =======================
    def _calendar_availability(self, item_index: int):
        """Check calendar availability (free/busy) according to the UI."""
        try:
            access_token = self._get_access_token()

            # ---- Calendar selection (same shape as other ops) ----
            cal_param = self.get_node_parameter("calendar", item_index, {})
            if not cal_param:
                raise ValueError("Calendar parameter not provided")
            calendar_id=googleCalendar_norm._resolve_calendar_id(cal_param)
           

            # ---- Required time window ----
            time_min = self.get_node_parameter("timeMin", item_index, "") or ""
            time_max = self.get_node_parameter("timeMax", item_index, "") or ""
            if not time_min or not time_max:
                raise ValueError("Both Start Time (timeMin) and End Time (timeMax) are required")

            # Optional sanity check (does not parse TZ strictly; relies on API for strict RFC3339)
            if time_min >= time_max:
                raise ValueError("Start Time must be earlier than End Time")

            # ---- Options: timezone, output format ----
            opts = self.get_node_parameter("options", item_index, {}) or {}
            timezone_opt   = (opts.get("timezone") or "UTC").strip()
            output_format  = (opts.get("outputFormat") or "availability").strip()  # availability|bookedSlots|raw

            # ---- Google freeBusy endpoint (note: /freeBusy, not under /calendars) ----
            url = f"{self._base_url}/freeBusy"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            body = {
                "timeMin": time_min,
                "timeMax": time_max,
                "timeZone": timezone_opt,
                "items": [{"id": calendar_id}],
            }

            resp = requests.post(url, headers=headers, json=body, timeout=30)
            if resp.status_code != 200:
                raise ValueError(f"Free/busy API failed ({resp.status_code}): {resp.text}")

            data = resp.json()
            cal = (data.get("calendars") or {}).get(calendar_id) or {}
            busy = cal.get("busy") or []   # list of {"start": "...", "end": "..."}

            # ---- Output shaping per UI ----
            if output_format == "raw":
                # Return entire API response for maximum transparency
                return {
                    "calendarId": calendar_id,
                    # "window": {"start": time_min, "end": time_max, "timeZone": timezone_opt},
                    "raw": data,
                }

            if output_format == "bookedSlots":
                return {
                    "calendarId": calendar_id,
                    # "window": {"start": time_min, "end": time_max, "timeZone": timezone_opt},
                    "busy": busy,
                    "busyCount": len(busy),
                }

            # Default: boolean availability (true if no overlaps)
            available = len(busy) == 0
            return {
                "calendarId": calendar_id,
                # "window": {"start": time_min, "end": time_max, "timeZone": timezone_opt},
                "available": available,
                "busyCount": len(busy),
            }

        except Exception as e:
            logger.error(f"Error checking calendar availability: {e}", exc_info=True)
            raise
