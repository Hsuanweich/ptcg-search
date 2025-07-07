import os
os.environ["TORCH_USE_RTLD_GLOBAL"] = "1"
os.environ["TORCH_DISABLE_MKL"] = "1"
os.environ["DNNL_VERBOSE"] = "1"
import torch
torch.backends.mkldnn.enabled = False
torch.backends.nnpack.enabled = False
import shutil
from torchvision import models, transforms
from PIL import Image
from PIL import PngImagePlugin
PngImagePlugin.MAX_TEXT_CHUNK = 1000000000
import csv

"""
***************************************************************************
建議在c槽創建一個ptcg_cards資料夾，並在裡面創建ptcgpicture和classify子資料夾
ptcgpicture:爬蟲圖片丟進這個
classify:分類後的圖片在這
將mobilenet_v2_finetuned_1.pth下載到classify中
***************************************************************************
"""
device = torch.device("cpu")
def classifymain():
    # 定義圖像轉換，應根據你的模型設置
    transform = transforms.Compose([
        transforms.Resize((224, 224)),  # 調整圖像大小以符合模型輸入
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    # 加載 MobileNet v2 模型架構
    mobilenet_v2 = models.mobilenet_v2(weights=None).to(device)  # 不使用預訓練權重

    # 修改最後的分類層，根據類別數（與訓練時的類別數保持一致）
    num_classes = 5  # 假設有5個類別，根據實際情況修改
    mobilenet_v2.classifier[1] = torch.nn.Linear(mobilenet_v2.last_channel, num_classes)


    # 加載訓練過的模型權重
    mobilenet_v2.load_state_dict(torch.load("/home/ptcg/PTCGHTML/ptcg_cards/classify/mobilenet_v2_finetuned_1.pth", map_location=torch.device('cpu')))
    """
    ***************************************************************************
    "C:\\ptcg_cards\\classify\\mobilenet_v2_finetuned_1.pth"
    改成你放mobilenet_v2_finetuned_1.pth的位置
    建議創一樣的路徑，就不用改
    ***************************************************************************
    """

    # 設定為推理模式
    mobilenet_v2.eval()  # 推理模式，不會更新權重

    # 指定圖片資料夾路徑
    image_folder = "/home/ptcg/PTCGHTML/official_card_image"
    """
    ***************************************************************************
    "/home/ptcg/PTCGHTML/official_card_image"
    改成你放所有爬蟲到的圖片的資料夾位置
    建議創一樣的路徑，就不用改
    ***************************************************************************
    """

    # 獲取資料夾中的所有圖片
    image_files = os.listdir(image_folder)

    # 設定分類後的儲存路徑
    output_folder = "/home/ptcg/PTCGHTML/ptcg_cards/classify"
    """
    ***************************************************************************
    "/home/ptcg/PTCGHTML/ptcg_cards/classify"
    改成你想放分類後圖片的資料夾位置
    建議創一樣的路徑，就不用改
    ***************************************************************************
    """

    # 創建類別資料夾，如果不存在則創建
    for i in range(num_classes):
        class_folder = os.path.join(output_folder, f'class_{i}')
        os.makedirs(class_folder, exist_ok=True)

    # 用來存儲預測結果的列表
    results = []

    # 對每張圖片進行分類
    for image_file in image_files:
        image_path = os.path.join(image_folder, image_file)

        # 加載圖片
        try:
            image = Image.open(image_path).convert('RGB')
        except ValueError as e:
            print(f"圖片 {image_path} 發生錯誤，跳過: {e}")
            continue

        # 進行圖片轉換
        input_tensor = transform(image).unsqueeze(0).to(device).float()  # 增加一個 batch 維度
        
        # 模型預測
        with torch.no_grad():
            output = mobilenet_v2(input_tensor)
            _, predicted_class = torch.max(output, 1)
            predicted_class = predicted_class.item()

        # 儲存圖片名稱和預測的類別
        results.append([image_file, predicted_class])

        # 將圖片複製到對應類別資料夾
        class_folder = os.path.join(output_folder, f'class_{predicted_class}')
        shutil.copy(image_path, class_folder)

        # 打印當前圖片的名稱和預測類別
        print(f"Image: {image_file} | Predicted Class: {predicted_class}")

    # 將結果寫入 CSV 檔案
    output_csv = "/home/ptcg/PTCGHTML/ptcg_cards/classify/classification_results.csv"
    """
    ***************************************************************************
    "C:\\ptcg_cards\\classify\\classification_results.csv"
    改成你想放分類後圖片CSV的位置
    建議創一樣的路徑，就不用改
    ***************************************************************************
    """
    with open(output_csv, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Image Name', 'Predicted Class'])
        writer.writerows(results)

    print(f"分類結果已儲存至 {output_csv}")

# classifymain()