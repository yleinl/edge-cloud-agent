import sys

import cv2
import numpy as np
import requests
import time


def handle(req):
    startTime = time.time()
    # Open a connection to the URL
    url = req
    response = requests.get(url, stream=True)
    response.raise_for_status()  # Ensure the request was successful

    image_array = np.asarray(bytearray(response.content), dtype=np.uint8)

    # Decode the image array using OpenCV
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    original_height, original_width = image.shape[:2]
    resized_image = cv2.resize(image, (original_height * 2, original_width * 2))

    endTime = time.time()

    # Calculate and print the time taken
    elaspedFunTime = "Total time to execute the function is: " + str(endTime-startTime) + " seconds"
    return elaspedFunTime


if __name__ == "__main__":
    req = sys.stdin.read()
    res = handle(req)
    print(res)
