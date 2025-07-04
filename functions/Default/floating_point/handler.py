import time as t
from math import sin, pi
import sys


def handle(req):
    """This function will calculate sine(360) multiple times"""
    startTime = t.time()
    for i in range(601):
        for x in range(361):
            result = sin(x*pi/180)
    endTime = t.time()
    elaspedFunTime = "Total time to execute the function is: " + str(endTime-startTime) + " seconds"
    return elaspedFunTime


if __name__ == "__main__":
    req = sys.stdin.read()
    res = handle(req)
    print(res)