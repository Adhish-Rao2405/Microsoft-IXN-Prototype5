from pathlib import Path
from onnxruntime.quantization import quantize_dynamic, QuantType

src = Path("models_custom/qwen2_5_0_5b_fp16/model.onnx")
out_dir = Path("models_custom/qwen2_5_0_5b_int8_ort_dynamic")
out_dir.mkdir(parents=True, exist_ok=True)
dst = out_dir / "model.int8.onnx"

if not src.exists():
    raise FileNotFoundError(f"Missing source ONNX model: {src}")

quantize_dynamic(
    model_input=str(src),
    model_output=str(dst),
    weight_type=QuantType.QInt8
)

print(f"INT8 dynamic quantized model saved to: {dst}")
