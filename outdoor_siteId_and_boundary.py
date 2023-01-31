from flask import Flask,abort,jsonify,make_response,request
import pymongo
import numpy as np
import json
from pymongo.database import Database


def mongodb_init():
    #connect to mongodb
    mongo = pymongo.MongoClient(host='XX.XXX.XX.XXX',port=27017,username="XXXX",password="XXXX",authSource='XXXX')
    print('数据库当前的databases: ', mongo.list_database_names())
    return mongo


def get_db(mongo, db_name):
    db = Database(name = db_name, client=mongo)
    print('获取/创建库：', db.name)
    return db


def Check_Inside(poi, boundary):
    # poi: [lon, lat] 
    # boundary: [[lon, lat], [lon, lat], [lon, lat],...]

    px = poi[0]
    py = poi[1]
    is_in = False
    for i, corner in enumerate(boundary):
        next_i = i + 1 if i + 1 < len(boundary) else 0
        x1, y1 = corner
        x2, y2 = boundary[next_i]
        if (x1 == px and y1 == py) or (x2 == px and y2 == py):  # if point is on vertex
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


app = Flask(__name__)
 
@app.route('/outdoor_siteId_and_boundary/<minlon>/<minlat>/<maxlon>/<maxlat>')
def outdoor_siteId_and_boundary(minlon,minlat,maxlon,maxlat):
    minlon = float(minlon)
    minlat = float(minlat)
    maxlon = float(maxlon)
    maxlat = float(maxlat)
    rect = [[minlon, minlat],[maxlon, maxlat]]
    
    mongo = mongodb_init()
    db = get_db(mongo,'loc_db')
    
    Reture_data = {}
    Data = []
    New = {} 
    OutdoorSiteCollection = db.OutdoorSite.find()

    for OutdoorSite in OutdoorSiteCollection:
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


if __name__ == '__main__':
    app.run()