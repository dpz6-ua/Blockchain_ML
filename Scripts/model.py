import torch.nn as nn
import torch.nn.functional as F
import pandas as pd
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
import torch

class NetCliente(nn.Module):
    def __init__(self):
        super(NetCliente, self).__init__()
        self.conv1 = nn.Conv2d(3, 32, 3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, 3, padding=1)
        self.pool = nn.MaxPool2d(2, 2)
        
        self.fc1 = nn.Linear(64 * 8 * 8, 128)
        self.fc2 = nn.Linear(128, 4)

    def forward(self, x):
        x = self.pool(F.relu(self.conv1(x))) # salida: 32x32x32
        x = self.pool(F.relu(self.conv2(x))) # salida: 64x16x16
        x = x.view(-1, 64 * 8 * 8)
        x = F.relu(self.fc1(x))
        return self.fc2(x)

class TrafficDataset(Dataset):
    def __init__(self, csv_file, transform=None):
        self.data_info = pd.read_csv(csv_file)
        self.transform = transform
        self.label_map = {
            'accident': 0,
            'dense_traffic': 1,
            'meteorology': 2,
            'sparse_traffic': 3
        }

    def __len__(self):
        return len(self.data_info)

    def __getitem__(self, idx):
        img_path = self.data_info.iloc[idx, 0]
        label_name = self.data_info.iloc[idx, 1]
        
        image = Image.open(img_path).convert('RGB')
        label = self.label_map[label_name]

        if self.transform:
            image = self.transform(image)

        return image, label
    
def load_data(csv_path):
    transform = transforms.Compose([
        transforms.Resize((32, 32)),
        transforms.ToTensor(),
        transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
    ])
    full_dataset = TrafficDataset(csv_file=csv_path, transform=transform)
    train_size = int(0.8 * len(full_dataset))
    test_size = len(full_dataset) - train_size
    train_ds, test_ds = torch.utils.data.random_split(full_dataset, [train_size, test_size])
    
    return DataLoader(train_ds, batch_size=16, shuffle=True), DataLoader(test_ds, batch_size=32)