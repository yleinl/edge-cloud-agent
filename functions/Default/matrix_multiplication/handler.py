import time as t
import numpy as np
import sys


def handle(req):
    """This function will calculate sine(360) multiple times"""
    startTime = t.time()
    size = 1024
    A = np.random.rand(size, size)
    B = np.random.rand(size, size)
    C = np.dot(A, B)
    endTime = t.time()
    elaspedFunTime = "Total time to execute the function is: " + str(endTime-startTime) + " seconds"
    return elaspedFunTime


if __name__ == "__main__":
    req = sys.stdin.read()
    res = handle(req)
    print(res)