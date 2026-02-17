import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser, Scale
from PIL import Image, ImageFilter, ImageTk, ImageEnhance, ImageOps, ImageDraw, ImageFont
import os
import cv2
import numpy as np
#from pathlib import Path
from datetime import datetime


class UltraImageEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Ultra Image Editor – 2025 Edition")
        self.root.geometry("1280x820")
        self.root.configure(bg="#e9ecef")

        self.original = None
        self.current = None
        self.photo = None
        self.undo_stack = []
        self.redo_stack = []
        self.history_limit = 12

        self.text_mode = False
        self.text_color = "black"
        self.text_size = 32
        self.draw_pos = None

        self.batch_last_op = None   # for batch re-apply
        self.face_cascade = None    # lazy load

        self._build_ui()
        self._load_face_cascade()

    def _load_face_cascade(self):
        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
        except:  # noqa: E722
            self.face_cascade = None
            print("Warning: Could not load face cascade – face blur disabled")

    def _build_ui(self):
        # ── Toolbar Top ────────────────────────────────────────
        topbar = tk.Frame(self.root, bg="#343a40", pady=6)
        topbar.pack(fill=tk.X)

        for txt, cmd, bg in [
            ("Open", self.open_image, "#495057"),
            ("Save", self.save_image, "#495057"),
            ("Reset", self.reset, "#6c757d"),
            ("Undo", self.undo, "#007bff"),
            ("Redo", self.redo, "#28a745"),
        ]:
            tk.Button(topbar, text=txt, command=cmd, bg=bg, fg="white",
                      font=("Segoe UI", 10, "bold"), width=8).pack(side=tk.LEFT, padx=4)

        tk.Button(topbar, text="Batch Process Folder", command=self.batch_process,
                  bg="#fd7e14", fg="white", font=("Segoe UI", 10, "bold")).pack(side=tk.RIGHT, padx=8)

        # ── Left Panel (now scrollable) ─────────────────────────
        left_outer = tk.Frame(self.root, bg="#f8f9fa", width=280)
        left_outer.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=8)

        left_canvas = tk.Canvas(left_outer, bg="#f8f9fa", highlightthickness=0)
        left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(left_outer, orient="vertical", command=left_canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        left_inner = tk.Frame(left_canvas, bg="#f8f9fa")
        left_inner.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        )

        left_canvas.create_window((0, 0), window=left_inner, anchor="nw")
        left_canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel support (Windows/macOS + Linux)
        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        left_canvas.bind_all("<MouseWheel>", _on_mousewheel)                    # Win/mac
        left_canvas.bind_all("<Button-4>", lambda e: left_canvas.yview_scroll(-1, "units"))  # Linux up
        left_canvas.bind_all("<Button-5>", lambda e: left_canvas.yview_scroll(1, "units"))   # Linux down

        # ── All controls now go into left_inner ─────────────────
        self._section(left_inner, "Core Adjustments")
        tk.Button(left_inner, text="Grayscale", command=self.grayscale).pack(fill=tk.X, pady=2)
        tk.Button(left_inner, text="Sharpen", command=self.sharpen).pack(fill=tk.X, pady=2)

        self._section(left_inner, "Blur & Face Blur")
        tk.Button(left_inner, text="Blur Faces (OpenCV)", command=self.blur_faces, bg="#dc3545", fg="white").pack(fill=tk.X, pady=4)
        self.blur_radius = self._scale(left_inner, "Blur Radius", 1, 25, 5, self.live_blur)

        self._section(left_inner, "Enhance")
        self.brightness = self._scale(left_inner, "Brightness", 0.3, 3.0, 1.0, self.enhance_live)
        self.contrast   = self._scale(left_inner, "Contrast",   0.3, 3.0, 1.0, self.enhance_live)

        self._section(left_inner, "Filters")
        filters = [
            ("Sepia", self.sepia),
            ("Vintage", self.vintage),
            ("Solarize", self.solarize),
            ("Posterize", self.posterize),
        ]
        for name, cmd in filters:
            tk.Button(left_inner, text=name, command=cmd, width=18).pack(pady=2)

        self._section(left_inner, "Rotate / Resize")
        rot_frame = tk.Frame(left_inner, bg="#f8f9fa")
        rot_frame.pack(fill=tk.X, pady=4)
        for deg in [90, -90, 180]:
            tk.Button(rot_frame, text=f"{deg}°", command=lambda d=deg: self.rotate(d)).pack(side=tk.LEFT, padx=3)

        self._section(left_inner, "Text Tool")
        text_ctrl = tk.Frame(left_inner, bg="#f8f9fa")
        text_ctrl.pack(fill=tk.X, pady=6)

        tk.Button(text_ctrl, text="Add Text", command=self.toggle_text_mode,
                  bg="#ffc107" if not self.text_mode else "#28a745", fg="black").pack(side=tk.LEFT)

        tk.Button(text_ctrl, text="Color", command=self.choose_text_color).pack(side=tk.LEFT, padx=4)

        tk.Label(text_ctrl, text="Size:", bg="#f8f9fa").pack(side=tk.LEFT)
        self.text_size_var = tk.IntVar(value=32)
        tk.Spinbox(text_ctrl, from_=12, to=120, textvariable=self.text_size_var, width=5).pack(side=tk.LEFT)

        tk.Label(left_inner, text="(Click image to place text)", fg="#6c757d", bg="#f8f9fa", font=("Segoe UI", 8)).pack(pady=4)

        # ── Canvas Area ────────────────────────────────────────
        self.canvas_frame = tk.Frame(self.root, bg="#ffffff")
        self.canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.canvas = tk.Canvas(self.canvas_frame, bg="white", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>", self.canvas_click)
        self.canvas.bind("<Configure>", lambda e: self.update_preview())

        # Zoom controls
        zoom_bar = tk.Frame(self.canvas_frame, bg="#f1f3f5")
        zoom_bar.pack(fill=tk.X)
        tk.Button(zoom_bar, text="+", command=self.zoom_in, width=3).pack(side=tk.RIGHT)
        tk.Button(zoom_bar, text="−", command=self.zoom_out, width=3).pack(side=tk.RIGHT)
        self.zoom_level = 1.0

        # Status
        self.status_var = tk.StringVar(value="Ready – Open an image")
        tk.Label(self.root, textvariable=self.status_var, bg="#dee2e6", anchor="w",
                 font=("Segoe UI", 9)).pack(side=tk.BOTTOM, fill=tk.X)

    def _section(self, parent, title):
        tk.Label(parent, text=title, font=("Segoe UI", 11, "bold"),
                 bg="#f8f9fa", fg="#495057").pack(anchor="w", pady=(12,4))

    def _scale(self, parent, label, from_, to, default, callback):
        frame = tk.Frame(parent, bg="#f8f9fa")
        frame.pack(fill=tk.X, pady=3)
        tk.Label(frame, text=label, width=12, anchor="w", bg="#f8f9fa").pack(side=tk.LEFT)
        s = Scale(frame, from_=from_, to=to, resolution=0.1 if to > 5 else 1,
                  orient=tk.HORIZONTAL, length=140, command=callback)
        s.set(default)
        s.pack(side=tk.LEFT)
        return s

    # ────────────────────────────────────────────────────────────────
    #   Core Image Management
    # ────────────────────────────────────────────────────────────────

    def push_undo(self):
        if self.current:
            self.undo_stack.append(self.current.copy())
            if len(self.undo_stack) > self.history_limit:
                self.undo_stack.pop(0)
            self.redo_stack.clear()

    def undo(self):
        if len(self.undo_stack) > 0:
            self.redo_stack.append(self.current.copy())
            self.current = self.undo_stack.pop()
            self.update_preview()
            self.status_var.set("Undo")

    def redo(self):
        if len(self.redo_stack) > 0:
            self.undo_stack.append(self.current.copy())
            self.current = self.redo_stack.pop()
            self.update_preview()
            self.status_var.set("Redo")

    def reset(self):
        if self.original:
            self.current = self.original.copy()
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.update_preview()
            self.status_var.set("Reset to original")

    def open_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp")])
        if not path: return  # noqa: E701
        try:
            self.original = Image.open(path).convert("RGB")
            self.current = self.original.copy()
            self.push_undo()
            self.zoom_level = 1.0
            self.update_preview()
            self.status_var.set(f"Opened: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def update_preview(self):
        if not self.current: return  # noqa: E701

        self.canvas.delete("all")

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10: return  # noqa: E701

        w, h = self.current.size
        nw = int(w * self.zoom_level)
        nh = int(h * self.zoom_level)

        resized = self.current.resize((nw, nh), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(resized)

        self.canvas.create_image(cw//2, ch//2, image=self.photo, anchor="center")
        self.canvas.image = self.photo

    def zoom_in(self):
        self.zoom_level *= 1.25
        self.update_preview()

    def zoom_out(self):
        self.zoom_level /= 1.25
        if self.zoom_level < 0.2: self.zoom_level = 0.2  # noqa: E701
        self.update_preview()

    # ────────────────────────────────────────────────────────────────
    #   Adjustments & Filters
    # ────────────────────────────────────────────────────────────────

    def grayscale(self):
        self.push_undo()
        self.current = ImageOps.grayscale(self.current).convert("RGB")
        self.update_preview()

    def sharpen(self):
        self.push_undo()
        self.current = self.current.filter(ImageFilter.SHARPEN)
        self.update_preview()

    def live_blur(self, val):
        if not self.current: return  # noqa: E701
        r = float(val)
        temp = self.current.filter(ImageFilter.GaussianBlur(r))
        self.current = temp
        self.update_preview()

    def enhance_live(self, _):
        if not self.original: return  # noqa: E701
        img = self.original.copy()
        img = ImageEnhance.Brightness(img).enhance(self.brightness.get())
        img = ImageEnhance.Contrast(img).enhance(self.contrast.get())
        self.current = img
        self.update_preview()

    def sepia(self):
        self.push_undo()
        width, height = self.current.size
        pixels = self.current.load()
        for x in range(width):
            for y in range(height):
                r, g, b = pixels[x, y]
                tr = int(0.393*r + 0.769*g + 0.189*b)
                tg = int(0.349*r + 0.686*g + 0.168*b)
                tb = int(0.272*r + 0.534*g + 0.131*b)
                pixels[x, y] = (min(tr,255), min(tg,255), min(tb,255))
        self.update_preview()

    def vintage(self):
        self.push_undo()
        self.current = ImageEnhance.Color(self.current).enhance(0.4)
        self.current = ImageEnhance.Brightness(self.current).enhance(1.15)
        self.current = ImageEnhance.Contrast(self.current).enhance(1.25)
        self.current = self.current.filter(ImageFilter.GaussianBlur(0.8))
        self.update_preview()

    def solarize(self):
        self.push_undo()
        self.current = ImageOps.solarize(self.current, threshold=128)
        self.update_preview()

    def posterize(self):
        self.push_undo()
        self.current = ImageOps.posterize(self.current, bits=4)
        self.update_preview()

    def rotate(self, degrees):
        self.push_undo()
        self.current = self.current.rotate(degrees, expand=True, fillcolor="white")
        self.update_preview()

    # ────────────────────────────────────────────────────────────────
    #   Face Detection + Blur
    # ────────────────────────────────────────────────────────────────

    def blur_faces(self):
        if not self.current or not self.face_cascade:
            messagebox.showwarning("Not available", "Face detection not loaded.")
            return

        self.push_undo()
        opencv_img = cv2.cvtColor(np.array(self.current), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(opencv_img, cv2.COLOR_BGR2GRAY)

        faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)

        for (x,y,w,h) in faces:
            face = opencv_img[y:y+h, x:x+w]
            blurred = cv2.GaussianBlur(face, (99,99), 30)
            opencv_img[y:y+h, x:x+w] = blurred

        self.current = Image.fromarray(cv2.cvtColor(opencv_img, cv2.COLOR_BGR2RGB))
        self.update_preview()
        self.status_var.set(f"Blurred {len(faces)} detected face(s)")

    # ────────────────────────────────────────────────────────────────
    #   Text Tool
    # ────────────────────────────────────────────────────────────────

    def toggle_text_mode(self):
        self.text_mode = not self.text_mode
        self.status_var.set("Text mode: " + ("ON – click to place" if self.text_mode else "OFF"))
        self.draw_pos = None

    def choose_text_color(self):
        color = colorchooser.askcolor(title="Choose Text Color")
        if color[1]:
            self.text_color = color[1]

    def canvas_click(self, event):
        if not self.text_mode or not self.current:
            return

        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.current.size
        scale = min(cw/iw, ch/ih) * self.zoom_level

        ox = (cw - iw * scale) / 2
        oy = (ch - ih * scale) / 2

        img_x = int((event.x - ox) / scale)
        img_y = int((event.y - oy) / scale)

        if 0 <= img_x < iw and 0 <= img_y < ih:
            self.push_undo()
            draw = ImageDraw.Draw(self.current)
            try:
                font = ImageFont.truetype("arial.ttf", self.text_size_var.get())
            except:  # noqa: E722
                font = ImageFont.load_default()

            text = tk.simpledialog.askstring("Text", "Enter text to add:")
            if text:
                draw.text((img_x, img_y), text, fill=self.text_color, font=font)
                self.update_preview()
                self.status_var.set("Text added")

    # ────────────────────────────────────────────────────────────────
    #   Batch Processing
    # ────────────────────────────────────────────────────────────────

    def batch_process(self):
        if not self.current:
            messagebox.showinfo("No reference", "Please process one image first.")
            return

        folder = filedialog.askdirectory(title="Select folder with images")
        if not folder:
            return

        out_folder = os.path.join(folder, f"edited_{datetime.now().strftime('%Y%m%d_%H%M')}")
        os.makedirs(out_folder, exist_ok=True)

        count = 0
        for file in os.listdir(folder):
            if file.lower().endswith((".jpg",".jpeg",".png",".bmp",".webp")):
                try:
                    path = os.path.join(folder, file)
                    img = Image.open(path).convert("RGB")
                    # Here we re-apply current state adjustments (simple version)
                    # You can extend this with your last filter / blur / etc.
                    processed = img.filter(ImageFilter.GaussianBlur(3))  # example – replace with your logic
                    processed.save(os.path.join(out_folder, f"processed_{file}"))
                    count += 1
                except:  # noqa: E722
                    pass

        messagebox.showinfo("Batch done", f"Processed {count} images\nSaved to:\n{out_folder}")

    def save_image(self):
        if not self.current:
            return  # noqa: E701
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            filetypes=[("PNG","*.png"),("JPEG","*.jpg")])
        if path:
            self.current.save(path, quality=92 if path.lower().endswith(".jpg") else None)
            self.status_var.set(f"Saved: {os.path.basename(path)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = UltraImageEditor(root)
    root.mainloop()