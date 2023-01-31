import json
from pathlib import Path
import os
import pandas

'''
    check if vertice within the polygon 
    poly: [[x1,y1],[x2,y2],……,[xn,yn]]
    poi: [lon, lat]
'''

def Check_point_inside_polygon(poi, poly):
    # 输入：点，多边形二维数组
    px = poi[0]
    py = poi[1]
    is_in = False
    for i, corner in enumerate(poly):
        next_i = i + 1 if i + 1 < len(poly) else 0
        x1, y1 = corner
        x2, y2 = poly[next_i]
        if (x1 == px and y1 == py) or (x2 == px and y2 == py):  # if point is on vertex
            is_in = True
            break
        if min(y1, y2) < py <= max(y1, y2):  # find horizontal edges of polygon
            x = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if x == px:  # if point is on edge
                is_in = True
                break
            elif x > px:  # if point is on left-side of line
                is_in = not is_in
    return is_in


'''
    check whether the upper and lower edges of a rectangle intersect with a line segment
    start: [lon, lat]
    end: [lon, lat]
    rectangle:[[minlon, minlat],[maxlon, maxlat]]
    lat: lat
'''


def Check_Rect_Line_H(start, end, lat, rect):
    if start[1] > lat and end[1] > lat:  # both points over line
        return False

    if start[1] < lat and end[1] < lat:  # both points below line
        return False

    if start[1] == end[1]:  # parallel
        if start[1] == lat:  # at same line
            if start[0] < rect[0][0] and end[0] < rect[0][0]:  # on the left
                return False
            if start[0] > rect[1][0] and end[0] > rect[1][0]:  # on the right
                return False
            return True
        else:  # not at same line
            return False

    # not parallel

    Lon = (end[0] - start[0]) * (lat - start[1]) / (end[1] - start[1]) + start[0]  # intersect point’s lon
    return rect[0][0] <= Lon <= rect[1][0]


'''
    check whether the right and left edges of a rectangle intersect with a line segment
    start: [lon, lat]
    end: [lon, lat]
    rectangle:[[minlon, minlat],[maxlon, maxlat]]
    lat: lon
'''


def Check_Rect_Line_V(start, end, lon, rect):
    if start[0] > lon and end[0] > lon:  # both points over line
        return False

    if start[0] < lon and end[0] < lon:  # both points below line
        return False

    if start[0] == end[0]:  # parallel
        if start[0] == lon:  # at same line
            if start[1] < rect[0][1] and end[1] < rect[0][1]:  # on the lower
                return False
            if start[1] > rect[1][1] and end[1] > rect[1][1]:  # on the upper
                return False
            return True
        else:  # not at same line
            return False

    # not parallel

    Lat = (end[1] - start[1]) * (lon - start[0]) / (end[0] - start[0]) + start[1]  # intersect point’s lat

    return rect[0][1] <= Lat <= rect[1][1]


'''
    check if four edges of a rectangle intersect with a line
    start: [lon, lat]
    end: [lon, lat]
    rectangle:[[minlon, minlat],[maxlon, maxlat]]

'''


def Check_Rect_Line(start, end, rect):
    flag = False
    if Check_point_inside_rect(start, rect) or Check_point_inside_rect(end, rect):
        flag = True
    else:  # check intersect with Rect’s 4 edges
        flag = flag or Check_Rect_Line_H(start, end, rect[0][1], rect)
        flag = flag or Check_Rect_Line_H(start, end, rect[1][1], rect)
        flag = flag or Check_Rect_Line_V(start, end, rect[0][0], rect)
        flag = flag or Check_Rect_Line_V(start, end, rect[1][0], rect)
    return flag


'''
    check if vertice within the rectangle
    rectangle:[[minlon, minlat],[maxlon, maxlat]]
    poi: [lon, lat]
'''


def Check_point_inside_rect(poi, rect):
    if rect[0][0] < poi[0] < rect[1][0] and rect[0][1] < poi[1] < rect[1][1]:
        return True
    return False


'''
    check if polygon intersect Rect
    rectangle:[[minlon, minlat],[maxlon, maxlat]]
    poly: [[x1,y1],[x2,y2],……,[xn,yn]]

'''


def Check_Rect_Poly(poly, rect):
    if len(poly) < 2 or rect[0][0] == rect[1][0] or rect[0][1] == rect[1][1]:
        return False
    index = 0
    print(rect)
    while index < len(poly) - 1:
        if Check_Rect_Line(poly[index], poly[index + 1], rect):
            return True
        index = index + 1
    return False


if __name__ == '__main__':
    # intersect
    poly = [
        [
            114.18957710266113,
            22.33435710728587
        ],
        [
            114.1838264465332,
            22.331022610018398
        ],
        [
            114.18459892272949,
            22.32610011121996
        ],
        [
            114.19120788574219,
            22.325147349455296
        ],
        [
            114.19678688049316,
            22.327370450118707
        ],
        [
            114.19549942016602,
            22.332769261386577
        ],
        [
            114.18957710266113,
            22.33435710728587
        ]
    ]
    # intersect
    rect_0 = [
        [
            114.18073654174805,
            22.327688033036043
        ],
        [
            114.18768882751465,
            22.333960147505827
        ]
    ]
    # outer
    rect_1 = [
        [
            114.15498733520508,
            22.32713226245626
        ],
        [
            114.16339874267578,
            22.33435710728587
        ]
    ]
    if Check_Rect_Poly(poly, rect_0):
        print("yeah! rect_0 correct")
    if not Check_Rect_Poly(poly, rect_1):
        print("yeah! rect_1 correct")
