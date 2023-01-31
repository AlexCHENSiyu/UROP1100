from flask import Flask,abort,jsonify,make_response,request
import pymongo
import numpy as np
import json
from pymongo.database import Database
 
 
def mongodb_init():
    #connect to mongodb
    mongo = pymongo.MongoClient(host='18.163.119.250',port=27017,username="root",password="1647#4hkust",authSource='admin')
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


app = Flask(__name__)
 
@app.route('/indoor_buildingId_and_boundary/<longitude>/<latitude>/<accuracy>')
def indoor_buildingId_and_boundary(longitude,latitude,accuracy):
    longitude = float(longitude)
    latitude = float(latitude)
    accuracy = float(accuracy)
    mongo = mongodb_init()
    db = get_db(mongo,'loc_db')
    
    Reture_data = {}
    Data = []
    New = {}
    buildingCollection = db.LocSetting.find({'BuildingID':{"$ne":None}})

    for building in buildingCollection:
        Intersect = False
        Inside = False
        boundary = building['Boundary']
        for num in range(len(boundary)-1): 
            if(Detect_Intersection(boundary[num], boundary[num+1], [longitude, latitude], accuracy)):
                Intersect = True
        if (not Intersect):
            Inside = Check_Inside([longitude, latitude], boundary) 
        if (Intersect or Inside):
            New['BuildingID'] = building['BuildingID']
            New['Boundary'] = building['Boundary']
            Data.append(New)
            Reture_data['data'] = Data
    return json.dumps(Reture_data,ensure_ascii=False)


if __name__ == '__main__':
    app.run()