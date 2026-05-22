import os
import shutil
import random
import cv2
import yaml
import logging
import argparse
from pathlib import Path
from typing import List, Tuple, Dict

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProductDatasetPreparer:
    """
    Validates, splits, and packages YOLO datasets for specific product codes
    without overwriting other products.
    """
    def __init__(self, base_source_dir: Path, output_base_dir: Path, train_ratio: float = 0.8, seed: int = 42):
        self.base_source_dir = base_source_dir
        self.output_base_dir = output_base_dir
        self.train_ratio = train_ratio
        self.seed = seed
        
    def validate_yolo_label(self, label_path: Path) -> bool:
        """
        Validates the format and values of a YOLO label file (class 0, coords between 0 and 1).
        """
        try:
            if not label_path.exists() or label_path.stat().st_size == 0:
                return False
                
            with open(label_path, 'r', encoding='utf-8') as f:
                lines = f.read().strip().split('\n')
                
            valid_lines = 0
            for line in lines:
                parts = line.strip().split()
                if len(parts) != 5:
                    continue
                    
                class_id = int(parts[0])
                coords = [float(x) for x in parts[1:]]
                
                # Class 0 is expected for hand detection
                if class_id != 0:
                    continue
                    
                # Coordinates must be normalized between 0.0 and 1.0
                if all(0.0 <= c <= 1.0 for c in coords):
                    valid_lines += 1
                    
            return valid_lines > 0
        except Exception as e:
            logger.debug(f"Error validating label {label_path}: {e}")
            return False

    def scan_folder(self, folder_path: Path) -> List[Tuple[Path, Path]]:
        """
        Scans a directory for matching, valid image-label pairs.
        """
        valid_pairs = []
        corrupted_images = 0
        mismatched_files = 0
        invalid_labels = 0
        
        all_files = list(folder_path.glob("*"))
        image_extensions = ['.jpg', '.jpeg', '.png']
        image_files = [f for f in all_files if f.suffix.lower() in image_extensions]
        
        for img_path in image_files:
            txt_path = img_path.with_suffix('.txt')
            if not txt_path.exists():
                mismatched_files += 1
                continue
                
            img = cv2.imread(str(img_path))
            if img is None:
                corrupted_images += 1
                continue
                
            if not self.validate_yolo_label(txt_path):
                invalid_labels += 1
                continue
                
            valid_pairs.append((img_path, txt_path))
            
        logger.info(f"Folder: {folder_path.name}")
        logger.info(f"  - Valid pairs: {len(valid_pairs)}")
        logger.info(f"  - Missing label or image files: {mismatched_files}")
        logger.info(f"  - Corrupted images: {corrupted_images}")
        logger.info(f"  - Invalid label files: {invalid_labels}")
        
        return valid_pairs

    def process(self, code: str) -> None:
        """
        Processes dataset for a specific product code (or merges all if code is 'merge').
        """
        random.seed(self.seed)
        logger.info(f"=== STARTING DATASET PREPARATION FOR CODE: {code} ===")
        
        # 1. Determine directories to scan
        folders_to_scan: List[Path] = []
        
        if code.lower() in ['merge', 'all', 'hopnhat']:
            # Scan all subdirectories
            if not self.base_source_dir.exists():
                logger.error(f"Source directory does not exist: {self.base_source_dir}")
                return
            subdirs = [d for d in self.base_source_dir.iterdir() if d.is_dir()]
            folders_to_scan.extend(subdirs)
            output_name = "dataset_hop_nhat"
        else:
            # Scan only the folder corresponding to the product code
            target_folder = self.base_source_dir / code
            if not target_folder.exists() or not target_folder.is_dir():
                logger.error(f"Dataset folder for code '{code}' does not exist at: {target_folder}")
                available = [d.name for d in self.base_source_dir.iterdir() if d.is_dir()]
                logger.error(f"Available codes: {available}")
                return
            folders_to_scan.append(target_folder)
            output_name = f"dataset_{code}"
            
        if not folders_to_scan:
            logger.error("No dataset directories to scan!")
            return
            
        logger.info(f"Scanning folders: {[f.name for f in folders_to_scan]}")
        
        # 2. Collect valid pairs
        all_valid_pairs: List[Tuple[Path, Path, str]] = []
        for folder in folders_to_scan:
            valid_pairs = self.scan_folder(folder)
            for img_path, txt_path in valid_pairs:
                all_valid_pairs.append((img_path, txt_path, folder.name))
                
        logger.info(f"Total valid pairs collected: {len(all_valid_pairs)}")
        if not all_valid_pairs:
            logger.error("No valid data found to process!")
            return
            
        # 3. Setup output folder
        output_dir = self.output_base_dir / output_name
        if output_dir.exists():
            logger.info(f"Purging old output directory: {output_dir}")
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 4. Split Train/Val
        random.shuffle(all_valid_pairs)
        split_idx = int(len(all_valid_pairs) * self.train_ratio)
        train_pairs = all_valid_pairs[:split_idx]
        val_pairs = all_valid_pairs[split_idx:]
        
        logger.info(f"Splitting data into {int(self.train_ratio*100)}/{int((1-self.train_ratio)*100)}:")
        logger.info(f"  - Train split: {len(train_pairs)} pairs")
        logger.info(f"  - Val split: {len(val_pairs)} pairs")
        
        # Create YOLO directories
        for split in ['train', 'val']:
            (output_dir / "images" / split).mkdir(parents=True, exist_ok=True)
            (output_dir / "labels" / split).mkdir(parents=True, exist_ok=True)
            
        # 5. Copy files
        logger.info("Copying and renaming dataset files...")
        for split, pairs in [('train', train_pairs), ('val', val_pairs)]:
            for i, (img_path, txt_path, prefix) in enumerate(pairs):
                safe_prefix = "".join([c if c.isalnum() else "_" for c in prefix])
                new_filename = f"hand_{safe_prefix}_{i:06d}"
                dest_img = output_dir / "images" / split / f"{new_filename}{img_path.suffix}"
                dest_txt = output_dir / "labels" / split / f"{new_filename}.txt"
                
                shutil.copy2(img_path, dest_img)
                shutil.copy2(txt_path, dest_txt)
                
        # 6. Generate dataset.yaml
        logger.info("Generating dataset.yaml...")
        abs_path = os.path.abspath(output_dir).replace("\\", "/")
        yaml_data = {
            'path': abs_path,
            'train': 'images/train',
            'val': 'images/val',
            'names': {
                0: 'hand'
            }
        }
        yaml_path = output_dir / "dataset.yaml"
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)
            
        logger.info(f"dataset.yaml created at: {yaml_path}")
        
        # 7. Zip directory
        zip_archive_base = self.output_base_dir / output_name
        logger.info(f"Zipping to {zip_archive_base}.zip...")
        zip_file_path = shutil.make_archive(
            base_name=str(zip_archive_base),
            format='zip',
            root_dir=str(output_dir)
        )
        logger.info(f"✅ ZIP file created successfully: {zip_file_path}")
        logger.info(f"=== COMPLETED PREPARING DATASET FOR {code} ===")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare dataset for a specific product code or merge all.")
    parser.add_argument('--code', type=str, default='626287', 
                        help="Product code to prepare (e.g. 626287). Use 'merge' to combine all folders.")
    
    args = parser.parse_args()
    
    source = Path("data/training_collection/extracted_data")
    destination = Path("projects/sop_monitoring/training")
    
    preparer = ProductDatasetPreparer(base_source_dir=source, output_base_dir=destination)
    preparer.process(args.code)
