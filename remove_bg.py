from PIL import Image

def make_transparent_white(img_path, out_path):
    img = Image.open(img_path)
    img = img.convert("RGBA")
    
    datas = img.getdata()
    newData = []
    
    # White background threshold
    for item in datas:
        # Check if the pixel is close to white (R, G, B > 230)
        if item[0] > 230 and item[1] > 230 and item[2] > 230:
            newData.append((255, 255, 255, 0)) # Make it transparent
        else:
            newData.append(item)
            
    img.putdata(newData)
    img.save(out_path, "PNG")

if __name__ == "__main__":
    make_transparent_white("static/img/favicon.jpg", "static/img/logo_transparent.png")
    print("Done")
