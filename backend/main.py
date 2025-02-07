from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from psd_tools import PSDImage
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import io
import base64

app = FastAPI()

# Configure CORS with more permissive settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Update this with your frontend URL
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "Content-Length"]
)

class TextLayer(BaseModel):
    name: str
    content: str
    font_name: Optional[str]
    font_size: Optional[float]
    color: Optional[str]
    alignment: Optional[str]
    styles: Optional[Dict[str, Any]]

class Layer(BaseModel):
    name: str
    type: str
    visible: bool
    opacity: Optional[float]
    blend_mode: Optional[str]
    position: Optional[Dict[str, Optional[float]]]
    effects: Optional[Dict[str, Any]] = {}  
    text_data: Optional[TextLayer]
    layer_image: Optional[str]

class PSDMetadata(BaseModel):
    filename: str
    width: int
    height: int
    resolution: float
    color_mode: str
    num_layers: int
    version: Optional[int]
    layers: List[Layer]
    preview_image: str

@app.post("/api/parse-psd")
async def parse_psd(file: UploadFile = File(...)) -> PSDMetadata:
    print(f"Received file: {file.filename}")
    if not file.filename.lower().endswith('.psd'):
        raise HTTPException(status_code=400, detail="File must be a PSD")
    
    try:
        # Read the uploaded file
        contents = await file.read()
        print(f"File size: {len(contents)} bytes")
        psd = PSDImage.open(io.BytesIO(contents))
        print(f"PSD opened successfully. Dimensions: {psd.width}x{psd.height}")
        
        # Generate composite image
        composite = psd.composite()
        img_byte_arr = io.BytesIO()
        composite.save(img_byte_arr, format='PNG')
        img_base64 = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
        print(f"Generated base64 preview image (length: {len(img_base64)})")

        # Process layers
        processed_layers = []
        for layer in psd.descendants():
            try:
                # Extract layer image if available
                layer_image = None
                if hasattr(layer, 'composite') and callable(layer.composite):
                    try:
                        layer_composite = layer.composite()
                        if layer_composite:
                            layer_img_byte_arr = io.BytesIO()
                            layer_composite.save(layer_img_byte_arr, format='PNG')
                            layer_image = base64.b64encode(layer_img_byte_arr.getvalue()).decode('utf-8')
                    except Exception as e:
                        print(f"Error extracting layer image for {layer.name}: {str(e)}")
                
                # Get layer position
                position = {
                    "x": getattr(layer, 'left', 0),
                    "y": getattr(layer, 'top', 0),
                    "width": getattr(layer, 'width', 0),
                    "height": getattr(layer, 'height', 0)
                }

                # Get text data if it's a text layer
                text_data = None
                if hasattr(layer, 'text_data') and layer.text_data:
                    text_data = TextLayer(
                        name=layer.name,
                        content=layer.text_data.get('text', ''),
                        font_name=layer.text_data.get('font', {}).get('name'),
                        font_size=layer.text_data.get('font', {}).get('size'),
                        color=layer.text_data.get('color'),
                        alignment=layer.text_data.get('alignment'),
                        styles=layer.text_data.get('style', {})
                    )

                # Create layer object
                layer_data = Layer(
                    name=layer.name,
                    type=getattr(layer, 'kind', 'pixel'),
                    visible=getattr(layer, 'visible', True),
                    opacity=getattr(layer, 'opacity', 255.0),
                    blend_mode=getattr(layer, 'blend_mode', 'normal'),
                    position=position,
                    effects={},
                    text_data=text_data,
                    layer_image=layer_image
                )
                processed_layers.append(layer_data)
            except Exception as e:
                print(f"Error processing layer {layer.name}: {str(e)}")
                continue

        # Create metadata
        metadata = PSDMetadata(
            filename=file.filename,
            width=psd.width,
            height=psd.height,
            resolution=getattr(psd, 'resolution', 72.0),
            color_mode=psd.color_mode.name if hasattr(psd, 'color_mode') else 'Unknown',
            num_layers=len(processed_layers),
            version=getattr(psd, 'version', None),
            layers=processed_layers,
            preview_image=f"data:image/png;base64,{img_base64}"
        )
        
        return metadata
    except Exception as e:
        print(f"Error processing PSD: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing PSD: {str(e)}")

@app.post("/api/modify-text")
async def modify_text(layer_name: str, new_text: str, file: UploadFile = File(...)):
    try:
        contents = await file.read()
        psd = PSDImage.open(io.BytesIO(contents))
        
        # Find and modify the text layer
        for layer in psd.descendants():
            if layer.name == layer_name and layer.kind == 'type':
                # Note: psd-tools doesn't support direct text modification
                # We would need to implement this using the Photoshop API
                # This is a placeholder for future implementation
                pass
        
        return {"message": "Text modification not supported yet"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
