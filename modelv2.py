import os
os.environ["TORCH_USE_RTLD_GLOBAL"] = "1"
os.environ["TORCH_DISABLE_MKL"] = "1"
os.environ["DNNL_VERBOSE"] = "1"
import numpy as np
import cv2
import torch
torch.backends.mkldnn.enabled = False
torch.backends.nnpack.enabled = False
import random
from torchvision import models, transforms
from PIL import Image, ImageEnhance
from PIL import PngImagePlugin
PngImagePlugin.MAX_TEXT_CHUNK = 1000000000
import pandas as pd
from sklearn.neighbors import NearestNeighbors
import torch.nn as nn
import torch.nn.functional as F
import pickle
import faiss

"""
錯誤訊息阻擋
"""
#import warnings
#warnings.simplefilter("ignore", UserWarning) # 隱藏UserWarning
#warnings.simplefilter("ignore", FutureWarning) # 隱藏FutureWarning

"""
自訓練裁切模型加載
"""
# 定義裁切模型
class CropModel(nn.Module):
    def __init__(self):
        super(CropModel, self).__init__()
        self.backbone = models.resnet18(pretrained=True)
        self.backbone.fc = nn.Linear(self.backbone.fc.in_features, 4)  # 預測 [x_min, y_min, x_max, y_max]

    def forward(self, x):
        return self.backbone(x)

# 設定裝置
device = torch.device("cpu")

# 加載裁切模型
model = CropModel()
model.load_state_dict(torch.load("/home/ptcg/PTCGHTML/ptcg_cards/card_crop_model_1.pth", map_location=device))  
model.to(device)
model.eval()  # 設置為推論模式
"""
***************************************************************************
將card_crop_model.pth下載到ptcg_cards中
***************************************************************************
"""

"""
自訓練分類模型加載
"""

# 加載 MobileNet v2 分類模型
mobilenet_v2 = models.mobilenet_v2(weights=None)
num_classes = 3  # 假設有 5 個類別
mobilenet_v2.classifier[1] = torch.nn.Linear(mobilenet_v2.last_channel, num_classes)
mobilenet_v2.load_state_dict(torch.load("/home/ptcg/PTCGHTML/ptcg_cards/classify/mobilenet_v2_finetuned_m3c.pth", map_location=torch.device('cpu')),strict=True )
mobilenet_v2.eval()
"""
***************************************************************************
classify中的mobilenet_v2_finetuned_1.pth
***************************************************************************
"""

class GeM(nn.Module):
    def __init__(self, p=3, eps=1e-6):
        super(GeM, self).__init__()
        self.p = nn.Parameter(torch.ones(1) * p)
        self.eps = eps

    def forward(self, x):
        return F.adaptive_avg_pool2d(x.clamp(min=self.eps).pow(self.p), (1, 1)).pow(1. / self.p)

modelrn50 = models.resnet101(weights=models.ResNet101_Weights.IMAGENET1K_V2)
modules = list(modelrn50.children())[:-2]
body = nn.Sequential(*modules)
modelrn50 = nn.Sequential(
    body,
    GeM(),                    # (B, 2048, 1, 1)
    nn.Flatten()              # 變成 (B, 2048)
)
modelrn50.eval()
modelrn50.to(device)


# 定義圖像轉換
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

"""
裁切模型預測與裁切函數
"""
# 預測與裁切函數
def predict_and_crop(model, image_path, transform, device='cpu'):
    model.eval()
    
    # 使用 OpenCV 讀取圖像
    image = cv2.imread(image_path)
    if image is None:
        print(f"讀不到圖片，請檢查路徑：{image_path}")
        return None  # 或跳錯誤，避免後續炸掉
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    h, w, _ = image.shape
    
    # 等比例縮放圖片，確保長邊為 640 像素
    if h > w:
        new_h, new_w = 640, int(w * 640 / h)
    else:
        new_h, new_w = int(h * 640 / w), 640
    image = cv2.resize(image, (new_w, new_h))
    
    # 轉換為 PIL 圖片
    image_pil = Image.fromarray(image)
    input_image = transform(image_pil).unsqueeze(0).to(device)

    with torch.no_grad():
        bbox = model(input_image).squeeze().cpu().numpy()

    # 取得裁切座標，並確保不超出範圍
    x_min, y_min, x_max, y_max = map(int, bbox)
    x_min, y_min = max(0, x_min), max(0, y_min)
    x_max, y_max = min(new_w, x_max), min(new_h, y_max)
    
    # 確保裁切區域有效
    if x_max <= x_min:
        x_max = x_min + 1
    if y_max <= y_min:
        y_max = y_min + 1

    # 裁切圖像
    cropped_image = image[y_min:y_max, x_min:x_max]
    return Image.fromarray(cropped_image)

# 圖像增強函數
def enhance_contrast_reduce_brightness(image, contrast_factor=1.5, brightness_factor=0.9):
    enhancer_contrast = ImageEnhance.Contrast(image)
    image_contrasted = enhancer_contrast.enhance(contrast_factor)
    enhancer_brightness = ImageEnhance.Brightness(image_contrasted)
    return enhancer_brightness.enhance(brightness_factor)

# 特徵提取與儲存函數
"""
def extract_features(images):
    model = ResNet50(weights='imagenet', include_top=False, pooling='avg')
    return model.predict(images)
"""

def extract_features(image_list, batch_size=32, device='cpu'):
    all_features = []

    with torch.no_grad():
        for i in range(0, len(image_list), batch_size):
            batch = image_list[i:i + batch_size]
            batch_tensor = torch.stack(batch).to(device)
            features = modelrn50(batch_tensor)  # shape: [B, 2048]
            all_features.append(features.cpu())

    return torch.cat(all_features, dim=0) 

def extract_single_image_feature(image, device='cpu'):
    preprocess = transforms.Compose([
        
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    # 如果是 numpy array（來自 cv2），轉成 PIL
    if isinstance(image, np.ndarray):
        image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    elif isinstance(image, str):
        image = Image.open(image).convert("RGB")
    else:
        raise ValueError("Unsupported image input type.")

    img_tensor = preprocess(image).unsqueeze(0).to(device)  # [1, 3, 224, 224]

    with torch.no_grad():
        feature = modelrn50(img_tensor)  # shape: [1, 2048]
        return feature.cpu()


# 讀取和處理圖像
def load_and_preprocess_images(image_folder):
    preprocess = transforms.Compose([
        
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    
    images = []
    file_paths = []

    for file_name in os.listdir(image_folder):
        file_path = os.path.join(image_folder, file_name)
        try:
            img = Image.open(file_path).convert('RGB')
            img_tensor = preprocess(img)
            images.append(img_tensor)
            file_paths.append(file_path)
        except Exception as e:
            print(f"⚠️ Failed to process {file_path}: {e}")
    
    return images, file_paths

"""
pickle特徵提取與儲存函數
"""
def save_features_to_pickle(image_folder, pickle_path, batch_size=32, device='cpu'):
    image_tensors, file_paths = load_and_preprocess_images(image_folder)  # 預處理過的 list of tensor
    features = extract_features(image_tensors, batch_size=batch_size, device=device)
    data = {"file_paths": file_paths, "features": features}
    
    with open(pickle_path, 'wb') as file:
        pickle.dump(data, file)
    
    print(f"✅ Features saved to {pickle_path}")

def load_features_from_pickle(pickle_path):
    try:
        with open(pickle_path, 'rb') as file:
            data = pickle.load(file)
            features = data['features']
            image_paths = data['file_paths']
        return features, image_paths
    except Exception as e:
        print(f"讀取Pickle文件時出錯: {e}")
        return None, None
    
"""
knn相似圖片搜索
"""
# 尋找相似圖片函數
def find_similar_images(query_image_path, image_folder, features_pickle_path, num_recommendations=5, model=None, device='cpu'):
    query_image = cv2.imread(query_image_path)
    features, file_paths = load_features_from_pickle(features_pickle_path)
    query_feature = extract_single_image_feature(query_image)

    print("query_feature shape:", query_feature.shape)
    print("features shape:", features.shape)

    knn = NearestNeighbors(n_neighbors=num_recommendations, metric='cosine')
    knn.fit(features)  # features shape: [N, 2048]
    distances, indices = knn.kneighbors(query_feature)

    return [file_paths[idx] for idx in indices[0]]


# 執行分類與圖像匹配

"""
***************************************************************************
"C:\\ptcg_cards\\phonephoto"為暫存資料夾
"C:\\ptcg_cards\\classify"為classify.py分類後資料夾的位置
***************************************************************************
"""
def modelmain(name):
    print(name + "開始分類")
    test_image_path = name #"/home/ptcg/PTCGHTML/ptcg_cards/primitivephonephoto/" + name + ".jpg"
    cropped_card = predict_and_crop(model, test_image_path, transform)
    #cropped_card.show()
    cropped_card.save("/home/ptcg/PTCGHTML/ptcg_cards/phonephoto/cropped_card-NEW.jpg")
    """
    執行分類與圖像匹配
    """
    image_folder = "/home/ptcg/PTCGHTML/ptcg_cards/phonephoto"
    classify_folder = "/home/ptcg/PTCGHTML/ptcg_cards/classify"
    random_images = random.sample(os.listdir(image_folder), 1) 
    for image_file in random_images:
        image_path = os.path.join(image_folder, image_file)
        image = Image.open(image_path).convert('RGB')
        image = enhance_contrast_reduce_brightness(image)
        input_tensor = transform(image).unsqueeze(0)
        
        with torch.no_grad():
            output = mobilenet_v2(input_tensor)
            _, predicted_class = torch.max(output, 1)
        
        class_folder = os.path.join(classify_folder, f'class_{predicted_class.item()}')
        features_pickle_path = os.path.join(classify_folder, f'features{predicted_class.item()}.pkl')
        
        if not os.path.exists(features_pickle_path):
            save_features_to_pickle(class_folder, features_pickle_path)
        
        recommended_images = find_similar_images(image_path, class_folder, features_pickle_path)
        best_match = recommended_images[0]

        print("Top recommended images:")
        for idx in recommended_images:
            print(idx)

        #return recommended_images
        
        """
        Image.open(best_match).show()
        """
        
        
        
name = "/home/ptcg/PTCGHTML/uploads/20250120_132406.jpg"
modelmain(name)