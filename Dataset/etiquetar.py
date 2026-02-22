import os
from pandas import DataFrame

def etiquetar_dataset(root_dir):
    data = []

    for folder_name in os.listdir(root_dir):
        folder_path = os.path.join(root_dir, folder_name)
        if os.path.isdir(folder_path):

            label = folder_name
            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)
                if os.path.isfile(file_path):
                    file_path = "../" + file_path
                    data.append([file_path, label])

    df = DataFrame(data, columns=['file_path', 'label'])

    csv_path = os.path.join(root_dir, 'dataset_etiquetado.csv')
    df.to_csv(csv_path, index=False)

    print(f"Labeled dataset saved to {csv_path}")

root_dir = 'Dataset/traffic-images'
etiquetar_dataset(root_dir)