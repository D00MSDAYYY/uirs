import numpy as np
import os
import re
import requests


def download_img(url=None, filename="ldem_64.img", save_path=None):
    """
    Скачивает файл ldem_64.img с сайта PDS Geosciences

    Parameters:
    -----------
    url : str, optional
        URL файла для скачивания. Если не указан, используется стандартный URL
    filename : str, optional
        Имя файла для сохранения (по умолчанию: ldem_64.img)
    save_path : str, optional
        Путь для сохранения файла. Если None, файл сохраняется в текущей директории

    Returns:
    --------
    str : полный путь к сохраненному файлу
    """

    # Стандартный URL если не указан другой
    if url is None:
        url = "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/DATA/LOLA_GDR/cylindrical/img/ldem_64.img"

    # Определяем путь для сохранения
    if save_path is None:
        save_path = os.path.join(os.getcwd(), filename)
    else:
        save_path = os.path.join(save_path, filename)

    try:
        print(f"Начинаю загрузку файла с URL: {url}")
        print(f"Файл будет сохранен как: {save_path}")

        # Отправляем GET запрос с потоковой передачей данных
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()  # Проверяем на ошибки HTTP

        # Получаем размер файла
        file_size = int(response.headers.get("content-length", 0))
        print(f"Размер файла: {file_size / (1024*1024):.2f} MB")

        # Скачиваем файл
        with open(save_path, "wb") as file:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
                    downloaded += len(chunk)

                    # Выводим прогресс
                    if file_size > 0:
                        percent = (downloaded / file_size) * 100
                        print(
                            f"Прогресс: {percent:.1f}% ({downloaded/(1024*1024):.1f}/{file_size/(1024*1024):.1f} MB)",
                            end="\r",
                        )

        print(f"\nФайл успешно скачан: {save_path}")
        return save_path

    except requests.exceptions.RequestException as e:
        print(f"Ошибка при скачивании файла: {e}")
        return None
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        return None


def parse_pds_label(label_file):
    """Парсит PDS .lbl файл и извлекает параметры данных"""

    params = {}

    try:
        with open(label_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Извлекаем ключевые параметры с помощью регулярных выражений
        patterns = {
            "lines": r"LINES\s*=\s*(\d+)",
            "line_samples": r"LINE_SAMPLES\s*=\s*(\d+)",
            "scaling_factor": r"SCALING_FACTOR\s*=\s*([\d\.]+)",
            "offset": r"OFFSET\s*=\s*([\d\.]+)",
            "sample_bits": r"SAMPLE_BITS\s*=\s*(\d+)",
            "file_records": r"FILE_RECORDS\s*=\s*(\d+)",
            "record_bytes": r"RECORD_BYTES\s*=\s*(\d+)",
            "map_resolution": r"MAP_RESOLUTION\s*=\s*(\d+)",
            "map_scale": r"MAP_SCALE\s*=\s*([\d\.]+)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    if key in ["scaling_factor", "offset", "map_scale"]:
                        params[key] = float(match.group(1))
                    else:
                        params[key] = int(match.group(1))
                except ValueError:
                    # Если не получается преобразовать в число, сохраняем как строку
                    params[key] = match.group(1)
                    print("err key", key)

        # Извлекаем строковые параметры
        string_patterns = {"file_name": r"FILE_NAME\s*=\s*\"([^\"]+)\""}

        for key, pattern in string_patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                params[key] = match.group(1)

        print("✓ Параметры успешно извлечены из PDS файла:")
        for key, value in params.items():
            print(f"  {key}: {value}")

        return params

    except Exception as e:
        print(f"✗ Ошибка чтения PDS файла: {e}")
        return None


def convert_ldem_to_meters(label_file):
    """Преобразует LDEM данные используя параметры из PDS .lbl файла"""
    params = parse_pds_label(label_file)

    # Основные параметры
    SCALING_FACTOR = params.get("scaling_factor")
    OFFSET = params.get("offset")
    NROWS = params.get("lines")
    NCOLS = params.get("line_samples")
    SAMPLE_BITS = params.get("sample_bits")
    input_file = params.get("file_name")

    output_file = os.path.splitext(label_file)[0] + "_meters.dat"

    # Проверяем существование файла
    if not os.path.exists(input_file):
        print(f"✗ Ошибка: файл {input_file} не найден!")
        return

    print(f"\n📊 Начинаем преобразование {input_file}...")
    print(f"   Размер: {NCOLS} × {NROWS} пикселей")
    print(f"   Формула: высота = (данные × {SCALING_FACTOR})")

    # Определяем тип данных на основе sample_bits
    if SAMPLE_BITS == 16:
        dtype = ">i2"  # big-endian int16
    else:
        dtype = ">i4"  # big-endian int32 (на случай других форматов)

    # Читаем бинарные данные
    print("📥 Чтение данных...")
    try:
        with open(input_file, "rb") as f:
            data = np.fromfile(f, dtype=dtype)
    except Exception as e:
        print(f"✗ Ошибка чтения файла: {e}")
        return

    # Проверяем размер данных
    expected_size = NCOLS * NROWS
    if len(data) != expected_size:
        print(
            f"⚠ Предупреждение: ожидалось {expected_size} значений, получено {len(data)}"
        )
        quit()

    # Изменяем форму массива
    data = data.reshape(NROWS, NCOLS)

    # Преобразование в метры - ВНИМАНИЕ: только умножение на scaling_factor!
    print("🔄 Преобразование в метры...")
    elevation_meters = data.astype(np.float32) * SCALING_FACTOR

    # Сохраняем результат
    print("💾 Сохранение результата...")
    elevation_meters.astype(np.float32).tofile(output_file)

    # Также сохраняем параметры для использования
    params_file = os.path.splitext(label_file)[0] + "_params.npy"
    np.save(params_file, params)
    print(f"✓ Параметры сохранены в {params_file}")

    return params


if __name__ == "__main__":
    download_img()
    # Указываем имя .lbl файла
    LBL_FILE = "ldem_64.lbl"
    params = convert_ldem_to_meters(LBL_FILE)
