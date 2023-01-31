from flask import Flask,abort,jsonify,make_response,request
import pymongo
import numpy as np
import json
from bson import json_util
import base64
from pymongo.database import Database
 
# Helper function
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def mongodb_init():
    #connect to mongodb
    mongo = pymongo.MongoClient(host='XX.XXX.XX.XXX',
                                port=27017,username="XXXX",
                                password="XXXX",
                                authSource='admin')
    print('数据库当前的databases: ', mongo.list_database_names())
    return mongo


def get_db(mongo, db_name):
    db = Database(name = db_name, client=mongo)
    print('获取/创建库：', db.name)
    return db


def Detect_Intersection(point1, point2, point, accuracy):
    #point:[longitude, latitude]
    
    X1 = point1[0] - point[0]
    Y1 = point1[1] - point[1]
    X2 = point2[0] - point[0]
    Y2 = point2[1] - point[1]
    R = accuracy

    A = np.square(X2-X1) + np.square(Y2-Y1)
    B = X1*(X2-X1) + Y1*(Y2-Y1)
    C = np.square(X1) + np.square(Y1) - np.square(R)
    Delta = B*B - A*C
    Intersection = False

    if (Delta > 0):
        t1 = (-B - np.sqrt(Delta)) / A
        t2 = (-B + np.sqrt(Delta)) / A
        if (t1<0 and 0<t2):
            Intersection = True
        elif (0<=t1 and t1<1):
            Intersection = True
        elif (1<=t1 and t1<t2):
            Intersection = False
    return Intersection


def Check_Inside(poi, boundary):
    # poi:[lon,lat]
    # boundary:[[lon,lat],...]
    
    px = poi[0]
    py = poi[1]
    is_in = False
    for i, corner in enumerate(boundary):
        next_i = i + 1 if i + 1 < len(boundary) else 0
        x1, y1 = corner
        x2, y2 = boundary[next_i]
        if (x1 == px and y1 == py) or (x2 == px and y2 == py):  
            # if point is on vertex
            is_in = True
            break
        if min(y1, y2) < py <= max(y1, y2):  
            # find horizontal edges of polygon
            x = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if x == px:  
                # if point is on edge
                is_in = True
                break
            elif x > px:  
                # if point is on left-side of line
                is_in = not is_in
    return is_in


def Check_Rect_Line_H(start, end, lat, rect):  
    # start: [lon, lat]  
    # end: [lon, lat] 
    # rectangle:[[minlon, minlat],[maxlon, maxlat]]
    # lat: lat

    if start[1] > lat and end[1] > lat:  
        # both points over line
        return False

    if start[1] < lat and end[1] < lat:  
        # both points below line
        return False

    if start[1] == end[1]:  
        # parallel
        if start[1] == lat:  
            # at same line
            if start[0] < rect[0][0] and end[0] < rect[0][0]: 
                # on the left
                return False
            if start[0] > rect[1][0] and end[0] > rect[1][0]:  
                # on the right
                return False
            return True
    else:  
        # not at same line
        return False

    # not parallel
    Lon = (end[0] - start[0]) * (lat - start[1]) / (end[1] - start[1]) + start[0]  # intersect point’s lon
    return rect[0][0] <= Lon <= rect[1][0]


def Check_Rect_Line_V(start, end, lon, rect):
    # start: [lon, lat]
    # end: [lon, lat]
    # lon: lon
    # rectangle:[[minlon, minlat],[maxlon, maxlat]]

    if start[0] > lon and end[0] > lon: 
        # both points over line
        return False

    if start[0] < lon and end[0] < lon:  
        # both points below line
        return False

    if start[0] == end[0]:  
        # parallel
        if start[0] == lon:  
            # at same line
            if start[1] < rect[0][1] and end[1] < rect[0][1]:  
                # on the lower
                return False
            if start[1] > rect[1][1] and end[1] > rect[1][1]:  
                # on the upper
                return False
            return True
    else:  
        # not at same line
        return False

    # not parallel
    Lat = (end[1] - start[1]) * (lon - start[0]) / (end[0] - start[0]) + start[1]  # intersect point’s lat

    return rect[0][1] <= Lat <= rect[1][1]


def Check_Rect_Line(start, end, rect):
    # start: [lon, lat]
    # end: [lon, lat]
    # rectangle:[[minlon, minlat],[maxlon, maxlat]]

    flag = False
    if Check_point_inside_rect(start, rect) or Check_point_inside_rect(end, rect):
        flag = True
    else:  
        # check intersect with Rect’s 4 edges
        flag = flag or Check_Rect_Line_H(start, end, rect[0][1], rect)
        flag = flag or Check_Rect_Line_H(start, end, rect[1][1], rect)
        flag = flag or Check_Rect_Line_V(start, end, rect[0][0], rect)
        flag = flag or Check_Rect_Line_V(start, end, rect[1][0], rect)
    return flag


def Check_point_inside_rect(poi, rect):
    # rectangle:[[minlon, minlat],[maxlon, maxlat]]
    # poi: [lon, lat]

    if rect[0][0] < poi[0] < rect[1][0] and rect[0][1] < poi[1] < rect[1][1]:
        return True
    return False


def Check_Rect_Poly(boundary, rect):
    # boundary: [[x1,y1],[x2,y2],……,[xn,yn]]
    # rectangle:[[minlon, minlat],[maxlon, maxlat]]

    if len(boundary) < 2 or rect[0][0] == rect[1][0] or rect[0][1] == rect[1][1]:
        return False
    index = 0
    while index < len(boundary) - 1:
        if Check_Rect_Line(boundary[index], boundary[index + 1], rect):
            return True
        index = index + 1
    return False


def get_map_json(MapDataIDs):
    map = []
    for mapId in MapDataIDs:
        P_newmap = db.Map.find({'MapID':mapId})
        for mapdata in P_newmap:
            del mapdata["_id"]
            del mapdata["createTime"]
            del mapdata["updateTime"]
            del mapdata['Data']
            map.append(mapdata)
    return map


# API below
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
app = Flask(__name__)

@app.route('/buildingId-and-boundary/<longitude>/<latitude>/<accuracy>')
def buildingId_and_boundary(longitude,latitude,accuracy):
    longitude = float(longitude)
    latitude = float(latitude)
    accuracy = float(accuracy)
    accuracy /= 2 * np.pi * 6378137 * np.cos(latitude/180*np.pi) / 360
    
    buildingCollection = db.LocSetting.find({'BuildingID':{"$ne":None}})
    
    Reture_data = {}
    Data = [] 
    for building in buildingCollection:
        New = {}
        Intersect = False
        Inside = False
        boundary = building['Boundary']
        for num in range(len(boundary)-1): 
            if(Detect_Intersection(boundary[num], boundary[num+1], [longitude, latitude], accuracy)):
                Intersect = True
        if (not Intersect):
            Inside = Check_Inside([longitude, latitude], boundary) 
        if (Intersect or Inside):
            New['buildingId'] = building['BuildingID']
            New['boundary'] = building['Boundary']
            Data.append(New)

    Reture_data['data'] = Data
    return json.dumps(Reture_data,ensure_ascii=False)
# http://127.0.0.1:5000/buildingId-and-boundary/114.26378/22.3351/0.0001582503318786621


@app.route('/building-loc-setting/<buildingId>')
def building_loc_setting(buildingId):
    P_LocSetting = db.LocSetting.find({'BuildingID':buildingId})
    
    Reture_data = {}
    Data = {}
    for LocSettingdata in P_LocSetting:
        del LocSettingdata["_id"]
        del LocSettingdata["createTime"]
        del LocSettingdata["updateTime"]
        Data['BuildingLocSetting'] = LocSettingdata
    
    Reture_data['data'] = Data
    return json.dumps(Reture_data,ensure_ascii=False)
# http://127.0.0.1:5000/building-loc-setting/4519721745T20220421


@app.route('/building-spatial-representation/<buildingId>')
def building_spatial_representation(buildingId):
    Reture_data = {}
    Data = {}
    Data['buildingId'] = buildingId
    P_building = db.Building.find({'BuildingID':buildingId})
    for buildingdata in P_building:
        del buildingdata["_id"]
        del buildingdata["createTime"]
        del buildingdata["updateTime"]
        Data['building'] = buildingdata
        if buildingdata.get("MapDataID","N/A") != "N/A":
            Data['mapJson'] = get_map_json(buildingdata["MapDataID"])
        else:
            Data['mapJson'] = []
            
        floors = []
        regions = []
        for floorNo in buildingdata['FloorList']:
            P_newfloor = db.Floor.find({'FloorNo':floorNo})
            newfloor = {}
            for floordata in P_newfloor:
                del floordata["_id"]
                del floordata["createTime"]
                del floordata["updateTime"]
                newfloor['floorId'] = floordata['FloorID']
                newfloor['floor'] = floordata
                if floordata.get("MapDataID","N/A") != "N/A":
                    newfloor['mapJson'] = get_map_json(floordata["MapDataID"])
                else:
                    newfloor['mapJson'] = []
                    
                for regionNo in floordata['RegionList']:
                    P_newregion = db.Region.find({'RegionNo':regionNo})
                    newregion = {}
                    for regiondata in P_newregion:
                        del regiondata["_id"]
                        del regiondata["createTime"]
                        del regiondata["updateTime"]
                        newregion['regionId'] = regiondata['RegionID']
                        newregion['region'] = regiondata
                        if regiondata.get("MapDataID","N/A") != "N/A":
                            newregion['mapJson'] = get_map_json(regiondata["MapDataID"])
                        else:
                            newregion['mapJson'] = []
                    regions.append(newregion)
            floors.append(newfloor)
            
        Data['floors'] = floors
        Data['regions'] = regions
        
    Reture_data['data'] = Data
    return json.dumps(Reture_data,ensure_ascii=False)
# http://127.0.0.1:5000/building-spatial-representation/4519721745T20220421
    

@app.route('/outdoor-siteId-and-boundary/<minLon>/<minLat>/<maxLon>/<maxLat>')
def outdoor_siteId_and_boundary(minLon,minLat,maxLon,maxLat):
    minLon = float(minLon)
    minLat = float(minLat)
    maxLon = float(maxLon)
    maxLat = float(maxLat)
    rect = [[minLon, minLat],[maxLon, maxLat]]
    
    OutdoorSiteCollection = db.OutdoorSite.find()
    
    Reture_data = {}
    Data = []
    for OutdoorSite in OutdoorSiteCollection:
        New = {}
        Intersect = False 
        Inside = False 
        boundary = OutdoorSite['Boundary']
        if Check_Rect_Poly(boundary, rect):
            Intersect = True
        if not Intersect:
            Inside = Inside or Check_Inside([rect[0][0], rect[0][1]], boundary) 
            Inside = Inside or Check_Inside([rect[0][0], rect[1][1]], boundary)
            Inside = Inside or Check_Inside([rect[1][0], rect[0][1]], boundary)
            Inside = Inside or Check_Inside([rect[1][0], rect[1][1]], boundary)
        if (Intersect or Inside):
            New['siteId'] = OutdoorSite['OutdoorSiteID']
            New['boundary'] = OutdoorSite['Boundary']
            Data.append(New)
            
    Reture_data['data'] = Data
    return json.dumps(Reture_data,ensure_ascii=False)
# http://127.0.0.1:5000/outdoor-siteId-and-boundary/114.20694/22.42694/114.20917/22.42972


@app.route('/outdoor-loc-setting/<siteId>')
def outdoor_loc_setting(siteId):
    P_OutdoorLocSetting = db.LocSetting.find({'OutdoorSiteID':siteId})
    
    Reture_data = {}
    Data = {}
    for OutdoorLocSettingData in P_OutdoorLocSetting:
        del OutdoorLocSettingData["_id"]
        del OutdoorLocSettingData["createTime"]
        del OutdoorLocSettingData["updateTime"]
        Data['OutdoorLocSetting'] = OutdoorLocSettingData
        
    Reture_data['data'] = Data
    return json.dumps(Reture_data,ensure_ascii=False)
# http://127.0.0.1:5000/outdoor-loc-setting/3984531850O20220423


@app.route('/map-metadata/')
def map_metadata():
    buildingId = request.args.get('buildingId') or "N/A"
    floorId = request.args.get('floorId') or "N/A"
    regionId = request.args.get('regionId') or "N/A"
    outdoorSiteId = request.args.get('outdoorSiteId') or "N/A"
    latitude = float(request.args.get('latitude') or -91)
    longitude = float(request.args.get('longitude') or -181)
    
    Reture_data = {}
    Data = {}
    if buildingId != "N/A":
        P_building = db.Building.find({'BuildingID':buildingId})
        for buildingdata in P_building:
            if buildingdata.get("MapDataID","N/A") != "N/A":
                Data["mapJson"] = get_map_json(buildingdata["MapDataID"])
    elif floorId != "N/A":
        P_floor = db.Floor.find({'FloorID':floorId})
        for floordata in P_floor:
            if floordata.get("MapDataID","N/A") != "N/A":
                Data["mapJson"] = get_map_json(floordata["MapDataID"])
    elif regionId != "N/A":
        P_region = db.Region.find({'RegionID':regionId})
        for regiondata in P_region:
            if regiondata.get("MapDataID","N/A") != "N/A":
                Data["mapJson"] = get_map_json(regiondata["MapDataID"])
    elif outdoorSiteId != "N/A":
        P_outdoorSite = db.OutdoorSite.find({'SiteID':outdoorSiteId})
        for outdoorSitedata in P_outdoorSite:
            if outdoorSitedata.get("MapDataID","N/A") != "N/A":
                Data["mapJson"] = get_map_json(outdoorSitedata["MapDataID"])
    elif latitude != -91 and longitude != -181:
        mapJson = []
        P_map = db.Map.find()
        for mapdata in P_map:
            if(Check_Inside([longitude,latitude],mapdata['Boundary'])):
                del mapdata["_id"]
                del mapdata["createTime"]
                del mapdata["updateTime"]
                del mapdata['Data']
                mapJson.append(mapdata)
        Data["mapJson"] = mapJson
        
    Reture_data['data'] = Data
    return json.dumps(Reture_data,ensure_ascii=False)
# http://127.0.0.1:5000/map-metadata/?floorId=4519721745T2022042184
# http://127.0.0.1:5000/map-metadata/?latitude=22.33506&longitude=114.26372


@app.route('/map/<mapId>')
def map(mapId):
    P_Map = db.Map.find({'MapID':mapId})
    
    Reture_data = {}
    Data = {}
    for MapData in P_Map:
        byte_base64 =  base64.b64encode(MapData["Data"])
        Data['mapData'] = byte_base64.decode('utf-8')
        # bytes_base64 = str_base64.encode('utf-8')
        # _bytes = base64.b64decode(bytes_base64)
        
    Reture_data['data'] = Data
    return Reture_data
# http://127.0.0.1:5000/map/f3dd32d9-0411-4cf4-945f-425bdddcc08e





if __name__ == '__main__':
    mongo = mongodb_init()
    db = get_db(mongo,'loc_db')
    app.run()