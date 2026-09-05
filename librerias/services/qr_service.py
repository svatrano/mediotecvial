import io
import qrcode
from PIL import Image

def generate_qr_image_bytes(data: str) -> io.BytesIO:
    """Genera una imagen QR en memoria como BytesIO (formato PNG)"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#1D3557", back_color="#FFFFFF")
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return img_io
