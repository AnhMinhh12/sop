import os
import shutil
import random
import zipfile
import yaml
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_ZIP_PATH = r"c:\Users\it07\Downloads\sop.yolov11.zip"
WORKSPACE_DIR = r"c:\Users\it07\Downloads\AI_Monitoring_Hub"
TEMP_EXTRACT_DIR = os.path.join(WORKSPACE_DIR, "training", "temp_extract")
OUTPUT_DIR = os.path.join(WORKSPACE_DIR, "training", "sop_yolov11_split")
OUTPUT_ZIP_PATH = r"c:\Users\it07\Downloads\sop_yolov11_split.zip"

TRAIN_RATIO = 0.8
VAL_RATIO = 0.1
TEST_RATIO = 0.1

def prepare():
    # 1. Check if the zip file exists
    if not os.path.exists(DEFAULT_ZIP_PATH):
        logger.error(f"Zip file not found at: {DEFAULT_ZIP_PATH}")
        # Search for other potential zip files in Downloads
        downloads_dir = r"c:\Users\it07\Downloads"
        zips = [os.path.join(downloads_dir, f) for f in os.listdir(downloads_dir) if f.endswith('.zip') and ('sop' in f.lower() or 'yolo' in f.lower())]
        if zips:
            logger.info(f"Found other potential zip files: {zips}")
            # Use the first one
            zip_path = zips[0]
            logger.info(f"Using {zip_path}")
        else:
            logger.error("No suitable zip file found in Downloads.")
            return
    else:
        zip_path = DEFAULT_ZIP_PATH

    logger.info(f"Starting split process for: {zip_path}")

    # 2. Clean previous directories if they exist
    for path in [TEMP_EXTRACT_DIR, OUTPUT_DIR]:
        if os.path.exists(path):
            logger.info(f"Cleaning existing directory: {path}")
            shutil.rmtree(path)
    
    os.makedirs(TEMP_EXTRACT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 3. Extract the zip file
    logger.info("Extracting zip file...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(TEMP_EXTRACT_DIR)
    logger.info("Extraction completed.")

    # 4. Find the dataset directories
    train_dir = None
    original_yaml_path = None
    
    for root, dirs, files in os.walk(TEMP_EXTRACT_DIR):
        if 'train' in dirs and os.path.exists(os.path.join(root, 'train', 'images')):
            train_dir = os.path.join(root, 'train')
        if 'data.yaml' in files:
            original_yaml_path = os.path.join(root, 'data.yaml')
            
    if not train_dir:
        logger.error("Could not find 'train/images' directory inside the extracted zip.")
        return
        
    src_images_dir = os.path.join(train_dir, "images")
    src_labels_dir = os.path.join(train_dir, "labels")

    logger.info(f"Found source images at: {src_images_dir}")
    logger.info(f"Found source labels at: {src_labels_dir}")

    # 5. Read classes from original data.yaml
    nc = 2
    names = ['hand', 'sp']
    if original_yaml_path and os.path.exists(original_yaml_path):
        try:
            with open(original_yaml_path, 'r', encoding='utf-8') as f:
                orig_data = yaml.safe_load(f)
                if orig_data:
                    nc = orig_data.get('nc', nc)
                    names = orig_data.get('names', names)
            logger.info(f"Successfully read classes from data.yaml: nc={nc}, names={names}")
        except Exception as e:
            logger.warning(f"Error reading original data.yaml: {e}. Using default classes: {names}")

    # 6. Gather all image files
    supported_extensions = ('.jpg', '.jpeg', '.png', '.bmp')
    images = [f for f in os.listdir(src_images_dir) if f.lower().endswith(supported_extensions)]
    if not images:
        logger.error(f"No images found in {src_images_dir}")
        return
        
    logger.info(f"Total images found: {len(images)}")
    
    # Shuffle images
    random.seed(42)  # For reproducibility
    random.shuffle(images)

    # 7. Calculate split indices
    total = len(images)
    train_end = int(total * TRAIN_RATIO)
    val_end = train_end + int(total * VAL_RATIO)
    
    train_images = images[:train_end]
    val_images = images[train_end:val_end]
    test_images = images[val_end:]
    
    splits = {
        'train': train_images,
        'val': val_images,
        'test': test_images
    }
    
    logger.info(f"Split sizes -> Train: {len(train_images)}, Val: {len(val_images)}, Test: {len(test_images)}")

    # 8. Copy files to the output directory
    for split_name, split_imgs in splits.items():
        logger.info(f"Copying {split_name} split...")
        dst_img_dir = os.path.join(OUTPUT_DIR, "images", split_name)
        dst_lbl_dir = os.path.join(OUTPUT_DIR, "labels", split_name)
        os.makedirs(dst_img_dir, exist_ok=True)
        os.makedirs(dst_lbl_dir, exist_ok=True)
        
        for img_name in split_imgs:
            # Copy image
            src_img_path = os.path.join(src_images_dir, img_name)
            dst_img_path = os.path.join(dst_img_dir, img_name)
            shutil.copy2(src_img_path, dst_img_path)
            
            # Copy corresponding label
            base_name, _ = os.path.splitext(img_name)
            label_name = base_name + ".txt"
            src_lbl_path = os.path.join(src_labels_dir, label_name)
            dst_lbl_path = os.path.join(dst_lbl_dir, label_name)
            
            if os.path.exists(src_lbl_path):
                shutil.copy2(src_lbl_path, dst_lbl_path)
            else:
                # If no label file, create an empty one (standard for YOLO background images)
                with open(dst_lbl_path, 'w') as f:
                    pass

    # 9. Create dataset.yaml for Colab
    dataset_yaml_content = {
        'path': '/content/sop_yolov11_split',
        'train': 'images/train',
        'val': 'images/val',
        'test': 'images/test',
        'nc': nc,
        'names': names
    }
    
    yaml_path = os.path.join(OUTPUT_DIR, "dataset.yaml")
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(dataset_yaml_content, f, default_flow_style=False, sort_keys=False)
    
    logger.info(f"Created dataset.yaml at {yaml_path}")

    # 10. Zip the output directory
    logger.info(f"Zipping output directory to {OUTPUT_ZIP_PATH}...")
    if os.path.exists(OUTPUT_ZIP_PATH):
        os.remove(OUTPUT_ZIP_PATH)
        
    with zipfile.ZipFile(OUTPUT_ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(OUTPUT_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, OUTPUT_DIR)
                zip_path_in_archive = os.path.join("sop_yolov11_split", rel_path).replace("\\", "/")
                zipf.write(file_path, zip_path_in_archive)

    logger.info("Zipping completed.")

    # 11. Clean up temp extraction & local output folder to save storage
    if os.path.exists(TEMP_EXTRACT_DIR):
        shutil.rmtree(TEMP_EXTRACT_DIR)
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    
    logger.info("\n" + "="*50)
    logger.info("🎉 DATASET PREPARATION COMPLETED!")
    logger.info(f"Original Zip: {zip_path}")
    logger.info(f"Processed Zip: {OUTPUT_ZIP_PATH}")
    logger.info(f"Train/Val/Test Split: {TRAIN_RATIO*100:.0f}% / {VAL_RATIO*100:.0f}% / {TEST_RATIO*100:.0f}%")
    logger.info(f"Classes: {names}")
    logger.info("="*50)
    logger.info("\nInstructions for Colab:")
    logger.info("1. Upload the file 'sop_yolov11_split.zip' to your Google Drive (MyDrive).")
    logger.info("2. Open Google Colab and run the training cell.")
    logger.info("="*50)

if __name__ == "__main__":
    prepare()

