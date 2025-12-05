from PIL import Image, ImageDraw

def create_image(filename, color, size=(100, 100)):
    img = Image.new('RGB', size, color=color)
    d = ImageDraw.Draw(img)
    # Removing text drawing here to avoid font dependency in this helper
    img.save(filename)

images = [
    ("img1.jpg", "red"),
    ("img2.jpg", "green"),
    ("img3.jpg", "blue"),
    ("img4.jpg", "purple")
]

for name, color in images:
    create_image(name, color, size=(1000, 1000))
    print(f"Created {name}")
