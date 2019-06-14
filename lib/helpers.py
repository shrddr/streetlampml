import cv2
import math
import random
import shutil
import os.path
import pathlib
import numpy as np

from lib import layers
from lib import loaders

def mil(fp):
    return math.floor(fp*1000000)

def osm_at_tile(tx, ty, z):
    # prints a link to open iD editor at specified tile
    lat, lng = layers.wgs_at_tile(tx, ty, z)
    print(f"https://www.openstreetmap.org/edit#map={z}/{lat}/{lng}")

def cleandir(path):
    # removes a directory and creates it again
    target = pathlib.Path(path)
    if os.path.isdir(target):
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    return target

def outside(point, lefttop, rightbot):
    return point[0] < lefttop[0] \
        or point[1] < lefttop[1] \
        or point[0] >= rightbot[0] \
        or point[1] >= rightbot[1]

class MercatorPainter:
    # paints an area with dots and lines representing positive examples.
    # everything not painted over is supposed to be negative.
    # uses dict for fast lookup (builds itself on first query).
    # also has a function to find a random negative (unpainted) pixel.
    def __init__(self, layer, W, S, E, N, z):   
        txmin, tymin = layer.tile_at_wgs((N, W), z)
        txmax, tymax = layer.tile_at_wgs((S, E), z)
        area = (txmax-txmin, tymax-tymin)
        print(f"paint area: {txmin}..{txmax}, {tymin}..{tymax}")
        print(f"dimensions: {area} -> {area[0]*area[1]} tiles total")
        
        self.z = z
        self.layer = layer
        self.txmin = txmin
        self.tymin = tymin
        self.width = txmax-txmin+1
        self.height = tymax-tymin+1
        self.canvas = np.zeros((self.height, self.width), np.uint8)
        
        self.dict = None
        self.dups = []
    
    def wgs2px(self, latlng):
        tx, ty = self.layer.tile_at_wgs(latlng, self.z)
        x = tx - self.txmin
        y = ty - self.tymin
        return (x,y)

    def add_dot_tile(self, tile, color=255):
        tx, ty = tile
        x = tx - self.txmin
        y = ty - self.tymin
        self.canvas[y][x] = color
            
    def add_dots_wgs(self, latlngs, color=255):
        for latlng in latlngs:
            x, y = self.wgs2px(latlng)
            self.canvas[y][x] = color
            
    def add_line_wgs(self, latlng1, latlng2, width):
        # the lines are actually curves in mercator but we don't care
        p1 = self.wgs2px(latlng1)
        p2 = self.wgs2px(latlng2)
        cv2.line(self.canvas, p1, p2, 255, width)
    
    def add_polyline_wgs(self, latlngs, width):
        pixels = [self.wgs2px(l) for l in latlngs]
        pixels = np.array(pixels)
        cv2.polylines(self.canvas, [pixels], False, 255, width)
        
    def show(self):
        cv2.imshow('canvas', self.canvas)
        cv2.waitKey(0)
    
    def reindex(self):
        d = {}
        for y in range(self.height):
            ty = self.tymin + y
            for x in range(self.width):
                tx = self.txmin + x
                if self.canvas[y][x] == 255:
                    if tx in d:
                        d[tx].append(ty)
                    else:
                        d[tx] = [ty]
        for k in d:
            d[k] = set(d[k])
        self.dict = d
        
    def contains(self, tile, result_outside=True):
        if self.dict is None:
            self.reindex()

        tx, ty = tile
        
        if tx < self.txmin or ty < self.tymin:
            return result_outside
        if tx >= self.txmin + self.width:
            return result_outside
        if ty >= self.tymin + self.height:
            return result_outside
        
        if tx in self.dict:
            if ty in self.dict[tx]:
                return True
        return False
    
    def random_negative(self):     
        # that's dumb maybe just walk through the dict?
        limit = 100
        count = 0
        while True:
            count += 1
            if count > limit:
                raise ValueError("too much retries")

            tx = random.randrange(self.txmin, self.txmin+self.width) 
            ty = random.randrange(self.tymin, self.tymin+self.height)
            tile = (tx, ty) 
            if self.contains(tile):
                continue
            else:
                self.add_dot_tile(tile)
                self.dict[tx].add(ty)
                return tile
        
if __name__ == "__main__":
#    box = (27.5682,53.8469,27.5741,53.8688) # south radius
    box = (27.4026,53.8306,27.7003,53.9739) # whole city
    lamps = loaders.query_nodes(*box)
    roads = loaders.query_ways(*box)
    
    mp = MercatorPainter(*box)
    mp.add_dots(lamps)  
    
    for nodes in roads.values():
        mp.add_polyline(nodes, width=2)
       
    mp.show()

    print(mp.contains((302304, 168755)))