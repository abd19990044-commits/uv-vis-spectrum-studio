from PIL import Image, ImageDraw

size = 256
img = Image.new("RGBA", (size, size), (15, 23, 42, 255))
d = ImageDraw.Draw(img)
d.rounded_rectangle((18, 18, 238, 238), radius=48, fill=(248, 250, 252, 255))
d.line((52, 196, 52, 56), fill=(51, 65, 85, 255), width=8)
d.line((52, 196, 210, 196), fill=(51, 65, 85, 255), width=8)
pts = [(58, 178), (78, 169), (96, 145), (112, 92), (126, 64), (138, 101), (151, 146), (168, 160), (188, 118), (205, 98)]
d.line(pts, fill=(37, 99, 235, 255), width=9, joint="curve")
d.line((126, 62, 126, 196), fill=(220, 38, 38, 180), width=4)
d.ellipse((118, 56, 134, 72), fill=(220, 38, 38, 255))
img.save("build_assets/app.ico", format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
