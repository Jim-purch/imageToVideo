from PIL import Image, ImageDraw

def create_image(filename, color, size=(100, 100)):
    img = Image.new('RGB', size, color=color)
    d = ImageDraw.Draw(img)
    d.text((10, 10), filename, fill=(255, 255, 255))
    img.save(filename)

images = [
    ("img1.jpg", "red"),
    ("img2.jpg", "green"),
    ("img3.jpg", "blue"),
    ("img4.jpg", "purple")
]

for name, color in images:
    create_image(name, color, size=(640, 480))
    print(f"Created {name}")
