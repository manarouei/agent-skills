import requests
import json
import logging
from typing import Dict, List, Optional, Any
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)


class NeshanNode(BaseNode):
    """
    Neshan node for map and location services
    """

    type = "neshan"
    version = 1.0

    description = {
        "displayName": "Neshan",
        "name": "neshan",
        "icon": "file:neshan.svg",
        "group": ["transform"],
        "description": "Access Neshan map and routing services",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "usableAsTool": True,
    }

    properties = {
        "credentials": [
            {
                "name": "neshanApi",
                "required": True,
            }
        ],
        "parameters": [
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Resource",
                "options": [
                    {"name": "Routing", "value": "routing"},
                    {"name": "Search", "value": "search"},
                ],
                "default": "routing",
                "description": "The resource category to operate on",
            },
            # Routing Operations
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Direction (With Traffic)", "value": "direction"},
                    {"name": "Direction (No Traffic)", "value": "directionNoTraffic"},
                    {"name": "Distance Matrix", "value": "distanceMatrix"},
                    {"name": "Distance Matrix (No Traffic)", "value": "distanceMatrixNoTraffic"},
                    {"name": "TSP (Trip Optimization)", "value": "tsp"},
                    {"name": "Isochrone", "value": "isochrone"},
                    {"name": "Map Matching", "value": "mapMatching"},
                    {"name": "Historical Routing", "value": "historicalRouting"},
                ],
                "default": "direction",
                "display_options": {"show": {"resource": ["routing"]}},
            },
            # Search Operations
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Search", "value": "search"},
                    {"name": "Geocoding", "value": "geocoding"},
                    {"name": "Geocoding Plus", "value": "geocodingPlus"},
                    {"name": "Reverse Geocoding", "value": "reverseGeocoding"},
                ],
                "default": "search",
                "display_options": {"show": {"resource": ["search"]}},
            },
            # Direction Parameters
            {
                "name": "type",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Vehicle Type",
                "options": [
                    {"name": "Car", "value": "car"},
                    {"name": "Motorcycle", "value": "motorcycle"},
                ],
                "default": "car",
                "description": "Type of vehicle",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["direction", "directionNoTraffic", "distanceMatrix", "distanceMatrixNoTraffic"],
                    }
                },
            },
            {
                "name": "origin",
                "type": NodeParameterType.STRING,
                "display_name": "Origin",
                "default": "",
                "required": True,
                "description": "Coordinates of the origin in latitude,longitude format (e.g., 35.7001,51.3882)",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["direction", "directionNoTraffic", "historicalRouting"],
                    }
                },
            },
            {
                "name": "destination",
                "type": NodeParameterType.STRING,
                "display_name": "Destination",
                "default": "",
                "required": True,
                "description": "Coordinates of the destination in latitude,longitude format (e.g., 35.7005,51.3895)",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["direction", "directionNoTraffic", "historicalRouting"],
                    }
                },
            },
            {
                "name": "waypoints",
                "type": NodeParameterType.STRING,
                "display_name": "Waypoints",
                "default": "",
                "description": "Intermediate points in lat,lng|lat,lng format (e.g., 35.7001,51.3882|35.7005,51.3895)",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["direction", "directionNoTraffic"],
                    }
                },
            },
            {
                "name": "avoidTrafficZone",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Avoid Traffic Zone",
                "default": False,
                "description": "Avoid traffic zones",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["direction", "directionNoTraffic", "historicalRouting"],
                    }
                },
            },
            {
                "name": "avoidOddEvenZone",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Avoid Odd-Even Zone",
                "default": False,
                "description": "Avoid odd-even traffic zones",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["direction", "directionNoTraffic"],
                    }
                },
            },
            {
                "name": "alternative",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Alternative Routes",
                "default": False,
                "description": "Get alternative routes",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["direction", "directionNoTraffic", "historicalRouting"],
                    }
                },
            },
            {
                "name": "bearing",
                "type": NodeParameterType.NUMBER,
                "display_name": "Bearing",
                "default": None,
                "description": "Starting angle of the route (0 to 360 degrees)",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["direction", "directionNoTraffic"],
                    }
                },
            },
            # Distance Matrix Parameters
            {
                "name": "origins",
                "type": NodeParameterType.STRING,
                "display_name": "Origins",
                "default": "",
                "required": True,
                "description": "List of origin coordinates in lat,lng|lat,lng format (e.g., 36.318,59.544|36.316,59.548)",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["distanceMatrix", "distanceMatrixNoTraffic"],
                    }
                },
            },
            {
                "name": "destinations",
                "type": NodeParameterType.STRING,
                "display_name": "Destinations",
                "default": "",
                "required": True,
                "description": "List of destination coordinates in lat,lng|lat,lng format (e.g., 36.338,59.474|36.340,59.466)",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["distanceMatrix", "distanceMatrixNoTraffic"],
                    }
                },
            },
            # TSP Parameters
            {
                "name": "tspWaypoints",
                "type": NodeParameterType.STRING,
                "display_name": "Waypoints",
                "default": "",
                "required": True,
                "description": "Points for route optimization in lat,lng|lat,lng format (e.g., 35.7001,51.3882|35.7005,51.3895)",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["tsp"],
                    }
                },
            },
            {
                "name": "roundTrip",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Round Trip",
                "default": True,
                "description": "Return to the starting point",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["tsp"],
                    }
                },
            },
            {
                "name": "sourceIsAnyPoint",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Source Is Any Point",
                "default": True,
                "description": "Automatically select the best starting point",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["tsp"],
                    }
                },
            },
            {
                "name": "lastIsAnyPoint",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Last Is Any Point",
                "default": True,
                "description": "Automatically select the best ending point",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["tsp"],
                    }
                },
            },
            # Isochrone Parameters
            {
                "name": "location",
                "type": NodeParameterType.STRING,
                "display_name": "Location",
                "default": "",
                "required": True,
                "description": "Center coordinates in lat,lng format (e.g., 35.736,51.375)",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["isochrone"],
                    }
                },
            },
            {
                "name": "distance",
                "type": NodeParameterType.NUMBER,
                "display_name": "Distance (km)",
                "default": None,
                "description": "Maximum reachable distance in kilometers",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["isochrone"],
                    }
                },
            },
            {
                "name": "time",
                "type": NodeParameterType.NUMBER,
                "display_name": "Time (minutes)",
                "default": None,
                "description": "Maximum reachable time in minutes",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["isochrone"],
                    }
                },
            },
            {
                "name": "polygon",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Polygon",
                "default": False,
                "description": "Get output as a Polygon (otherwise LineString)",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["isochrone"],
                    }
                },
            },
            {
                "name": "denoise",
                "type": NodeParameterType.NUMBER,
                "display_name": "Denoise",
                "default": 0,
                "description": "Simplification level of the boundary (0 to 1)",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["isochrone"],
                    }
                },
            },
            # Map Matching Parameters
            {
                "name": "path",
                "type": NodeParameterType.STRING,
                "display_name": "Path",
                "default": "",
                "required": True,
                "description": "GPS path in lat,lng|lat,lng format (minimum 2 and maximum 1000 points)",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["mapMatching"],
                    }
                },
            },
            # Historical Routing Parameters
            {
                "name": "routingType",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Routing Type",
                "options": [
                    {"name": "Depart At", "value": "DepartAt"},
                    {"name": "Arrive At", "value": "ArriveAt"},
                ],
                "default": "DepartAt",
                "description": "Calculation type based on departure or arrival time",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["historicalRouting"],
                    }
                },
            },
            {
                "name": "dateTime",
                "type": NodeParameterType.STRING,
                "display_name": "Date Time",
                "default": "",
                "required": True,
                "description": "Date and time in YYYY-MM-DDThh:mm format (e.g., 2025-03-18T14:00)",
                "display_options": {
                    "show": {
                        "resource": ["routing"],
                        "operation": ["historicalRouting"],
                    }
                },
            },
            # Search Parameters
            {
                "name": "term",
                "type": NodeParameterType.STRING,
                "display_name": "Search Term",
                "default": "",
                "required": True,
                "description": "Search term",
                "display_options": {
                    "show": {
                        "resource": ["search"],
                        "operation": ["search"],
                    }
                },
            },
            {
                "name": "lat",
                "type": NodeParameterType.NUMBER,
                "display_name": "Latitude",
                "default": 35.7,
                "required": True,
                "description": "Latitude of the search center",
                "display_options": {
                    "show": {
                        "resource": ["search"],
                        "operation": ["search", "reverseGeocoding"],
                    }
                },
            },
            {
                "name": "lng",
                "type": NodeParameterType.NUMBER,
                "display_name": "Longitude",
                "default": 51.4,
                "required": True,
                "description": "Longitude of the search center",
                "display_options": {
                    "show": {
                        "resource": ["search"],
                        "operation": ["search", "reverseGeocoding"],
                    }
                },
            },
            # Geocoding Parameters
            {
                "name": "address",
                "type": NodeParameterType.STRING,
                "display_name": "Address",
                "default": "",
                "required": True,
                "description": "Address to convert to coordinates",
                "display_options": {
                    "show": {
                        "resource": ["search"],
                        "operation": ["geocoding", "geocodingPlus"],
                    }
                },
            },
            {
                "name": "province",
                "type": NodeParameterType.STRING,
                "display_name": "Province",
                "default": "",
                "description": "Province (optional)",
                "display_options": {
                    "show": {
                        "resource": ["search"],
                        "operation": ["geocoding", "geocodingPlus"],
                    }
                },
            },
            {
                "name": "city",
                "type": NodeParameterType.STRING,
                "display_name": "City",
                "default": "",
                "description": "City (optional)",
                "display_options": {
                    "show": {
                        "resource": ["search"],
                        "operation": ["geocoding", "geocodingPlus"],
                    }
                },
            },
            {
                "name": "geocodingLocation",
                "type": NodeParameterType.STRING,
                "display_name": "Center Location",
                "default": "",
                "description": "Search center in lat,lng format (optional)",
                "display_options": {
                    "show": {
                        "resource": ["search"],
                        "operation": ["geocoding", "geocodingPlus"],
                    }
                },
            },
            {
                "name": "extent",
                "type": NodeParameterType.STRING,
                "display_name": "Extent (Bounding Box)",
                "default": "",
                "description": "Search area in swLat,swLng,neLat,neLng format (optional)",
                "display_options": {
                    "show": {
                        "resource": ["search"],
                        "operation": ["geocoding", "geocodingPlus"],
                    }
                },
            },
        ]
    }

    icon = "neshan.svg"
    color = "#00C853"

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Neshan operations and return properly formatted data"""
        try:
            # Get input data using the new method signature
            input_data = self.get_input_data()
            result_items: List[NodeExecutionData] = []

            # Process each input item
            for i, item in enumerate(input_data):
                try:
                    # Get parameters for this item
                    resource = self.get_node_parameter("resource", i, "routing")
                    operation = self.get_node_parameter("operation", i, "direction")

                    # Execute the appropriate operation
                    if resource == "routing":
                        if operation == "direction":
                            result = self._execute_direction(i, with_traffic=True)
                        elif operation == "directionNoTraffic":
                            result = self._execute_direction(i, with_traffic=False)
                        elif operation == "distanceMatrix":
                            result = self._execute_distance_matrix(i, with_traffic=True)
                        elif operation == "distanceMatrixNoTraffic":
                            result = self._execute_distance_matrix(i, with_traffic=False)
                        elif operation == "tsp":
                            result = self._execute_tsp(i)
                        elif operation == "isochrone":
                            result = self._execute_isochrone(i)
                        elif operation == "mapMatching":
                            result = self._execute_map_matching(i)
                        elif operation == "historicalRouting":
                            result = self._execute_historical_routing(i)
                        else:
                            raise ValueError(f"Unsupported operation '{operation}' for resource '{resource}'")

                    elif resource == "search":
                        if operation == "search":
                            result = self._execute_search(i)
                        elif operation == "geocoding":
                            result = self._execute_geocoding(i, plus=False)
                        elif operation == "geocodingPlus":
                            result = self._execute_geocoding(i, plus=True)
                        elif operation == "reverseGeocoding":
                            result = self._execute_reverse_geocoding(i)
                        else:
                            raise ValueError(f"Unsupported operation '{operation}' for resource '{resource}'")
                    else:
                        raise ValueError(f"Unsupported resource '{resource}'")

                    # Add result to items
                    result_items.append(
                        NodeExecutionData(json_data=result, binary_data=None)
                    )

                except Exception as e:
                    logger.error(f"Error in Neshan node execution: {str(e)}")
                    # Create error data following project pattern
                    error_item = NodeExecutionData(
                        json_data={
                            "error": str(e),
                            "resource": self.get_node_parameter("resource", i, "routing"),
                            "operation": self.get_node_parameter("operation", i, "direction"),
                            "item_index": i,
                        },
                        binary_data=None,
                    )
                    result_items.append(error_item)

            return [result_items]

        except Exception as e:
            error_data = [
                NodeExecutionData(
                    json_data={"error": f"Error in Neshan node: {str(e)}"},
                    binary_data=None,
                )
            ]
            return [error_data]

    def _get_api_credentials(self) -> tuple[str, str]:
        """Get Neshan API credentials"""
        credentials = self.get_credentials("neshanApi")
        if not credentials:
            raise ValueError("Neshan credentials not found")

        api_url = credentials.get("apiUrl", "https://api.neshan.org").rstrip('/')
        api_key = credentials.get("apiKey")

        if not api_key:
            raise ValueError("API key is required for Neshan API")

        return api_url, api_key

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with API key"""
        _, api_key = self._get_api_credentials()
        return {
            "Api-Key": api_key,
            "Content-Type": "application/json"
        }

    def _execute_direction(
        self,
        item_index: int,
        with_traffic: bool = True
    ) -> Dict[str, Any]:
        """Execute direction (routing) operation"""
        api_url, _ = self._get_api_credentials()
        headers = self._get_headers()

        vehicle_type = self.get_node_parameter("type", item_index, "car")
        origin = self.get_node_parameter("origin", item_index, "")
        destination = self.get_node_parameter("destination", item_index, "")
        waypoints = self.get_node_parameter("waypoints", item_index, "")
        avoid_traffic_zone = self.get_node_parameter("avoidTrafficZone", item_index, False)
        avoid_odd_even = self.get_node_parameter("avoidOddEvenZone", item_index, False)
        alternative = self.get_node_parameter("alternative", item_index, False)
        bearing = self.get_node_parameter("bearing", item_index, None)

        endpoint = "/v4/direction" if with_traffic else "/v4/direction/no-traffic"

        params = {
            "type": vehicle_type,
            "origin": origin,
            "destination": destination,
            "avoidTrafficZone": str(avoid_traffic_zone).lower(),
            "avoidOddEvenZone": str(avoid_odd_even).lower(),
            "alternative": str(alternative).lower(),
        }

        if waypoints:
            params["waypoints"] = waypoints
        if bearing is not None:
            params["bearing"] = bearing

        url = f"{api_url}{endpoint}"
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        return response.json()

    def _execute_distance_matrix(
        self,
        item_index: int,
        with_traffic: bool = True
    ) -> Dict[str, Any]:
        """Execute distance matrix operation"""
        api_url, _ = self._get_api_credentials()
        headers = self._get_headers()

        vehicle_type = self.get_node_parameter("type", item_index, "car")
        origins = self.get_node_parameter("origins", item_index, "")
        destinations = self.get_node_parameter("destinations", item_index, "")
        
        endpoint = "/v1/distance-matrix" if with_traffic else "/v1/distance-matrix/no-traffic"
        
        params = {
            "type": vehicle_type,
            "origins": origins,
            "destinations": destinations,
        }
        
        url = f"{api_url}{endpoint}"
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        return response.json()

    def _execute_tsp(
        self,
        item_index: int
    ) -> Dict[str, Any]:
        """Execute TSP (Traveling Salesman Problem) operation"""
        api_url, _ = self._get_api_credentials()
        headers = self._get_headers()

        waypoints = self.get_node_parameter("tspWaypoints", item_index, "")
        round_trip = self.get_node_parameter("roundTrip", item_index, True)
        source_is_any = self.get_node_parameter("sourceIsAnyPoint", item_index, True)
        last_is_any = self.get_node_parameter("lastIsAnyPoint", item_index, True)
        
        params = {
            "waypoints": waypoints,
            "roundTrip": str(round_trip).lower(),
            "sourceIsAnyPoint": str(source_is_any).lower(),
            "lastIsAnyPoint": str(last_is_any).lower(),
        }
        
        url = f"{api_url}/v3/trip"
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        return response.json()

    def _execute_isochrone(
        self,
        item_index: int
    ) -> Dict[str, Any]:
        """Execute isochrone operation"""
        api_url, _ = self._get_api_credentials()
        headers = self._get_headers()

        location = self.get_node_parameter("location", item_index, "")
        distance = self.get_node_parameter("distance", item_index, None)
        time = self.get_node_parameter("time", item_index, None)
        polygon = self.get_node_parameter("polygon", item_index, False)
        denoise = self.get_node_parameter("denoise", item_index, 0)
        
        if not distance and not time:
            raise ValueError("Either distance or time parameter is required")
        
        params = {
            "location": location,
            "polygon": str(polygon).lower(),
            "denoise": denoise,
        }
        
        if distance:
            params["distance"] = distance
        if time:
            params["time"] = time
        
        url = f"{api_url}/v1/isochrone"
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        return response.json()

    def _execute_map_matching(
        self,
        item_index: int
    ) -> Dict[str, Any]:
        """Execute map matching operation"""
        api_url, _ = self._get_api_credentials()
        headers = self._get_headers()

        path = self.get_node_parameter("path", item_index, "")
        
        payload = {
            "path": path
        }
        
        url = f"{api_url}/v3/map-matching"
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        return response.json()

    def _execute_historical_routing(
        self,
        item_index: int
    ) -> Dict[str, Any]:
        """Execute historical routing operation"""
        api_url, _ = self._get_api_credentials()
        headers = self._get_headers()

        origin = self.get_node_parameter("origin", item_index, "")
        destination = self.get_node_parameter("destination", item_index, "")
        routing_type = self.get_node_parameter("routingType", item_index, "DepartAt")
        date_time = self.get_node_parameter("dateTime", item_index, "")
        avoid_traffic_zone = self.get_node_parameter("avoidTrafficZone", item_index, False)
        alternative = self.get_node_parameter("alternative", item_index, False)
        
        params = {
            "origin": origin,
            "destination": destination,
            "routingType": routing_type,
            "dateTime": date_time,
            "avoidTrafficZone": str(avoid_traffic_zone).lower(),
            "alternative": str(alternative).lower(),
        }
        
        url = f"{api_url}/v1/direction/historical"
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        return response.json()

    def _execute_search(
        self,
        item_index: int
    ) -> Dict[str, Any]:
        """Execute location search operation"""
        api_url, _ = self._get_api_credentials()
        headers = self._get_headers()

        term = self.get_node_parameter("term", item_index, "")
        lat = self.get_node_parameter("lat", item_index, 35.7)
        lng = self.get_node_parameter("lng", item_index, 51.4)
        
        params = {
            "term": term,
            "lat": lat,
            "lng": lng,
        }
        
        url = f"{api_url}/v1/search"
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        return response.json()

    def _execute_geocoding(
        self,
        item_index: int,
        plus: bool = False
    ) -> Dict[str, Any]:
        """Execute geocoding operation"""
        api_url, _ = self._get_api_credentials()
        headers = self._get_headers()

        address = self.get_node_parameter("address", item_index, "")
        province = self.get_node_parameter("province", item_index, "")
        city = self.get_node_parameter("city", item_index, "")
        location_str = self.get_node_parameter("geocodingLocation", item_index, "")
        extent_str = self.get_node_parameter("extent", item_index, "")
        
        geo_params = {
            "address": address
        }
        
        if province:
            geo_params["province"] = province
        if city:
            geo_params["city"] = city
        
        if location_str:
            try:
                lat, lng = location_str.split(",")
                geo_params["location"] = {
                    "latitude": float(lat.strip()),
                    "longitude": float(lng.strip())
                }
            except:
                pass
        
        if extent_str:
            try:
                sw_lat, sw_lng, ne_lat, ne_lng = extent_str.split(",")
                geo_params["extent"] = {
                    "southWest": {"latitude": float(sw_lat.strip()), "longitude": float(sw_lng.strip())},
                    "northEast": {"latitude": float(ne_lat.strip()), "longitude": float(ne_lng.strip())}
                }
            except:
                pass
        
        endpoint = "/geocoding/v1/plus" if plus else "/geocoding/v1"
        
        params = {
            "json": json.dumps(geo_params)
        }
        
        url = f"{api_url}{endpoint}"
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        return response.json()

    def _execute_reverse_geocoding(
        self,
        item_index: int
    ) -> Dict[str, Any]:
        """Execute reverse geocoding operation"""
        api_url, _ = self._get_api_credentials()
        headers = self._get_headers()

        lat = self.get_node_parameter("lat", item_index, 35.7)
        lng = self.get_node_parameter("lng", item_index, 51.4)

        params = {
            "lat": lat,
            "lng": lng,
        }

        url = f"{api_url}/v5/reverse"
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        return response.json()
