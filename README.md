# Ultra Image Editor

A simple yet powerful desktop image editor built with **Python**, **Tkinter**, **Pillow (PIL)** and **OpenCV**.

https://github.com/TekFed/ultra-image-editor

![Screenshot of Ultra Image Editor](screenshots/filters.png)

## Features

- **Basic adjustments**
  - Grayscale conversion
  - Sharpen filter
  - Gaussian blur (with live radius slider)

- **Face detection & blur** (using OpenCV Haar cascade)
  - Automatically detects frontal faces and applies strong blur

- **Color & lighting enhancements**
  - Brightness & contrast sliders (live preview)

- **Artistic filters**
  - Sepia
  - Vintage look
  - Solarize
  - Posterize

- **Rotation**
  - 90°, -90°, 180° quick buttons
  - (Custom angle support can be easily added)

- **Text tool**
  - Click on image to place text
  - Choose color via color picker
  - Adjustable font size (12–120 pt)
  - Uses system fonts (falls back to default)

- **Zoom**
  - Zoom in / out buttons (canvas scaling)

- **Undo / Redo** (limited history – 12 steps)

- **Batch processing**
  - Apply simple processing (currently example blur) to entire folder

- **Save** with quality options (JPEG/PNG)

## Screenshots

| Main interface | Text tool in action | Face blur result |
|----------------|---------------------|------------------|
| ![Main](screenshots/filters.png) | ![Text](screenshots/blurry.png) | ![Faces](screenshots/face_blur.png) |

## Requirements

```bash
pip install pillow opencv-python

