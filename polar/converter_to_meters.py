import numpy as np
import os
import re
import requests
import warnings

warnings.filterwarnings("ignore")


def download_img(url=None, filename="ldem_45n_100m.img", save_path=None):
    """
    Скачивает файл с полярной стереографической проекцией

    Parameters:
    -----------
    url : str, optional
        URL файла для скачивания. Если не указан, используется стандартный URL
    filename : str, optional
        Имя файла для сохранения (по умолчанию: ldem_45n_100m.img)
    save_path : str, optional
        Путь для сохранения файла. Если None, файл сохраняется в текущей директории

    Returns:
    --------
    str : полный путь к сохраненному файлу
    """

    # Стандартный URL для полярных файлов (северное полушарие, 100м разрешение)
    if url is None:
        url = f"https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/DATA/LOLA_GDR/polar/img/ldem_45n_100m.img"

        # Если файл не найден по этому URL, можно поискать альтернативные
        print(f"⚠ Используется стандартный URL для полярного файла")
        print(f"ℹ Фактический URL может отличаться")
        print(f"ℹ Проверьте доступность файла на сайте PDS")

    # Определяем путь для сохранения
    if save_path is None:
        save_path = os.path.join(os.getcwd(), filename)
    else:
        save_path = os.path.join(save_path, filename)

    try:
        print(f"Начинаю загрузку файла с URL: {url}")
        print(f"Файл будет сохранен как: {save_path}")

        # Отправляем GET запрос с потоковой передачей данных
        response = requests.get(url, stream=True, timeout=60)
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
        print("\nПопробуйте найти файл вручную на сайте:")
        print("https://pds-geosciences.wustl.edu/lro/")
        return None
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        return None


def parse_polar_pds_label(label_file):
    """
    Парсит PDS .lbl файл для ПОЛЯРНОЙ стереографической проекции

    Parameters:
    -----------
    label_file : str
        Путь к файлу .lbl

    Returns:
    --------
    dict : словарь с параметрами
    """

    params = {}

    try:
        with open(label_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Определяем тип проекции
        if "POLAR STEREOGRAPHIC" not in content.upper():
            print("⚠ Внимание: Файл не использует полярную стереографическую проекцию!")
            print("  Используется другая проекция")

        # Извлекаем ключевые параметры с помощью регулярных выражений
        patterns = {
            # Основные параметры изображения
            "lines": r"LINES\s*=\s*(\d+)",
            "line_samples": r"LINE_SAMPLES\s*=\s*(\d+)",
            "scaling_factor": r"SCALING_FACTOR\s*=\s*([\d\.\-]+)",
            "offset": r"OFFSET\s*=\s*([\d\.\-]+)",
            "sample_bits": r"SAMPLE_BITS\s*=\s*(\d+)",
            # Параметры файла
            "file_records": r"FILE_RECORDS\s*=\s*(\d+)",
            "record_bytes": r"RECORD_BYTES\s*=\s*(\d+)",
            # Параметры проекции (особенно важные для полярной)
            "map_projection_type": r"MAP_PROJECTION_TYPE\s*=\s*\"([^\"]+)\"",
            "map_scale": r"MAP_SCALE\s*=\s*([\d\.]+)\s*<m/pix>",
            "center_latitude": r"CENTER_LATITUDE\s*=\s*([\d\.\-]+)\s*<deg>",
            "center_longitude": r"CENTER_LONGITUDE\s*=\s*([\d\.\-]+)\s*<deg>",
            "minimum_latitude": r"MINIMUM_LATITUDE\s*=\s*([\d\.\-]+)\s*<deg>",
            "maximum_latitude": r"MAXIMUM_LATITUDE\s*=\s*([\d\.\-]+)\s*<deg>",
            # Смещения проекции (ключевые для преобразования координат)
            "sample_projection_offset": r"SAMPLE_PROJECTION_OFFSET\s*=\s*([\d\.\-]+)\s*<pix>",
            "line_projection_offset": r"LINE_PROJECTION_OFFSET\s*=\s*([\d\.\-]+)\s*<pix>",
            # Радиусы осей
            "a_axis_radius": r"A_AXIS_RADIUS\s*=\s*([\d\.]+)\s*<km>",
            "b_axis_radius": r"B_AXIS_RADIUS\s*=\s*([\d\.]+)\s*<km>",
            "c_axis_radius": r"C_AXIS_RADIUS\s*=\s*([\d\.]+)\s*<km>",
            # Дополнительные параметры
            "derived_minimum": r"DERIVED_MINIMUM\s*=\s*([\d\.\-]+)",
            "derived_maximum": r"DERIVED_MAXIMUM\s*=\s*([\d\.\-]+)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    if key in [
                        "scaling_factor",
                        "offset",
                        "map_scale",
                        "center_latitude",
                        "center_longitude",
                        "minimum_latitude",
                        "maximum_latitude",
                        "sample_projection_offset",
                        "line_projection_offset",
                        "a_axis_radius",
                        "b_axis_radius",
                        "c_axis_radius",
                    ]:
                        params[key] = float(match.group(1))
                    elif key in ["derived_minimum", "derived_maximum"]:
                        params[key] = float(match.group(1))
                    elif key == "map_projection_type":
                        params[key] = match.group(1)
                    else:
                        params[key] = int(match.group(1))
                except ValueError:
                    # Если не получается преобразовать в число, сохраняем как строку
                    params[key] = match.group(1)

        # Извлекаем строковые параметры
        string_patterns = {
            "file_name": r"FILE_NAME\s*=\s*\"([^\"]+)\"",
            "product_id": r"PRODUCT_ID\s*=\s*\"([^\"]+)\"",
        }

        for key, pattern in string_patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                params[key] = match.group(1)

        # Заполняем значения по умолчанию для отсутствующих параметров
        defaults = {
            "sample_bits": 16,
            "scaling_factor": 0.5,
            "offset": 1737400.0,
            "a_axis_radius": 1737.4,
            "b_axis_radius": 1737.4,
            "c_axis_radius": 1737.4,
        }

        for key, default_value in defaults.items():
            if key not in params:
                params[key] = default_value

        print("✓ Параметры успешно извлечены из PDS файла:")
        print(f"  Проекция: {params.get('map_projection_type', 'не указана')}")
        print(
            f"  Размер: {params.get('lines', '?')} × {params.get('line_samples', '?')}"
        )
        print(f"  Разрешение: {params.get('map_scale', '?')} м/пиксель")
        print(
            f"  Центр: {params.get('center_latitude', '?')}°, {params.get('center_longitude', '?')}°"
        )
        print(
            f"  Диапазон широт: {params.get('minimum_latitude', '?')}° до {params.get('maximum_latitude', '?')}°"
        )

        return params

    except Exception as e:
        print(f"✗ Ошибка чтения PDS файла: {e}")
        return None


def convert_polar_ldem_to_meters(label_file, output_format="npz"):
    """
    Преобразует ПОЛЯРНЫЕ LDEM данные используя параметры из PDS .lbl файла

    Parameters:
    -----------
    label_file : str
        Путь к файлу .lbl
    output_format : str
        Формат вывода: "npz", "bin", "tif"
    """

    params = parse_polar_pds_label(label_file)
    if params is None:
        return

    # Основные параметры
    SCALING_FACTOR = params.get("scaling_factor", 0.5)
    OFFSET = params.get("offset", 1737400.0)
    NROWS = params.get("lines")
    NCOLS = params.get("line_samples")
    SAMPLE_BITS = params.get("sample_bits", 16)
    input_file = params.get("file_name")

    if input_file is None:
        # Попробуем определить имя файла из имени label файла
        input_file = os.path.splitext(label_file)[0] + ".img"
        print(f"ℹ Имя файла данных не указано, используем: {input_file}")

    # Создаем имя выходного файла
    base_name = os.path.splitext(label_file)[0]
    if output_format == "npz":
        output_file = base_name + "_meters.npz"
    elif output_format == "bin":
        output_file = base_name + "_meters.bin"
    elif output_format == "tif":
        output_file = base_name + "_meters.tif"
    else:
        output_file = base_name + "_meters.dat"

    # Проверяем существование файла
    if not os.path.exists(input_file):
        print(f"✗ Ошибка: файл {input_file} не найден!")
        print("ℹ Ищу файлы .img в текущей директории...")
        img_files = [f for f in os.listdir(".") if f.endswith(".img")]
        if img_files:
            print(f"Найдены файлы: {img_files}")
            input_file = img_files[0]
            print(f"Использую: {input_file}")
        else:
            return

    print(f"\n📊 Начинаем преобразование {input_file}...")
    print(f"   Размер: {NCOLS} × {NROWS} пикселей")
    print(
        f"   Проекция: {params.get('map_projection_type', 'Полярная стереографическая')}"
    )
    print(f"   Формула: высота = (данные × {SCALING_FACTOR})")
    print(f"   Радиус сферы: {OFFSET} м")

    # Определяем тип данных на основе sample_bits
    if SAMPLE_BITS == 16:
        dtype = "<i2"  # little-endian int16 (LSB_INTEGER в PDS)
    elif SAMPLE_BITS == 32:
        dtype = "<i4"  # little-endian int32
    else:
        dtype = "<i2"  # по умолчанию
        print(f"⚠ Неизвестный SAMPLE_BITS={SAMPLE_BITS}, используем int16")

    # Читаем бинарные данные
    print("📥 Чтение данных...")
    try:
        with open(input_file, "rb") as f:
            data = np.fromfile(f, dtype=dtype)
    except Exception as e:
        print(f"✗ Ошибка чтения файла: {e}")
        print("ℹ Пробую другой порядок байтов...")
        try:
            # Пробуем big-endian
            with open(input_file, "rb") as f:
                if SAMPLE_BITS == 16:
                    data = np.fromfile(f, dtype=">i2")
                else:
                    data = np.fromfile(f, dtype=">i4")
        except Exception as e2:
            print(f"✗ Ошибка чтения с big-endian: {e2}")
            return

    # Проверяем размер данных
    expected_size = NCOLS * NROWS
    if len(data) != expected_size:
        print(
            f"⚠ Предупреждение: ожидалось {expected_SIZE} значений, получено {len(data)}"
        )
        # Пробуем обрезать или дополнить
        if len(data) > expected_size:
            print(f"ℹ Обрезаем данные до {expected_size} значений")
            data = data[:expected_size]
        else:
            print(f"ℹ Данных недостаточно, возможно файл поврежден")
            return

    # Изменяем форму массива
    data = data.reshape(NROWS, NCOLS)

    # Преобразование в метры (относительно сферы радиуса OFFSET)
    print("🔄 Преобразование в метры...")
    elevation_meters = data.astype(np.float32) * SCALING_FACTOR

    # Также вычисляем абсолютную высоту (радиус)
    radius_meters = elevation_meters + OFFSET

    # Вычисляем статистику
    min_height = np.nanmin(elevation_meters)
    max_height = np.nanmax(elevation_meters)
    mean_height = np.nanmean(elevation_meters)

    print(f"📈 Статистика высот:")
    print(f"   Минимум: {min_height:.1f} м")
    print(f"   Максимум: {max_height:.1f} м")
    print(f"   Среднее: {mean_height:.1f} м")
    print(f"   Относительно сферы радиусом {OFFSET} м")

    # Сохраняем результат в выбранном формате
    print(f"💾 Сохранение результата как {output_format}...")

    if output_format == "npz":
        # Сохраняем как сжатый numpy файл с метаданными
        np.savez_compressed(
            output_file,
            elevation=elevation_meters,
            radius=radius_meters,
            metadata=params,
        )
        print(f"✓ Данные сохранены в {output_file}")
        print(f"  Доступны массивы: elevation (высоты), radius (радиусы), metadata")

    elif output_format == "bin":
        # Сохраняем как бинарный файл
        elevation_meters.astype(np.float32).tofile(output_file)
        print(f"✓ Данные сохранены в бинарный файл {output_file}")

    elif output_format == "tif":
        # Сохраняем как GeoTIFF (требуется rasterio)
        try:
            import rasterio
            from rasterio.transform import from_origin

            # Создаем transform для полярной проекции
            # Это упрощенное преобразование, для точного нужны параметры проекции
            map_scale = params.get("map_scale", 100.0)
            center_x_px = params.get("sample_projection_offset", NCOLS / 2)
            center_y_px = params.get("line_projection_offset", NROWS / 2)

            # Преобразование пиксель -> метр
            transform = from_origin(
                -center_x_px * map_scale, center_y_px * map_scale, map_scale, map_scale
            )

            with rasterio.open(
                output_file,
                "w",
                driver="GTiff",
                height=NROWS,
                width=NCOLS,
                count=1,
                dtype=elevation_meters.dtype,
                crs="+proj=stere +lat_0=90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +a=1737400 +b=1737400 +units=m +no_defs",
                transform=transform,
            ) as dst:
                dst.write(elevation_meters, 1)
                dst.update_tags(**params)

            print(f"✓ Данные сохранены как GeoTIFF {output_file}")

        except ImportError:
            print("✗ Для сохранения как GeoTIFF требуется rasterio")
            print("ℹ Установите: pip install rasterio")
            print("ℹ Сохраняю как бинарный файл вместо GeoTIFF")
            elevation_meters.astype(np.float32).tofile(
                output_file.replace(".tif", ".bin")
            )

    else:
        # Сохраняем как простой бинарный файл
        elevation_meters.astype(np.float32).tofile(output_file)
        print(f"✓ Данные сохранены в {output_file}")

    # Сохраняем также текстовый файл с метаданными
    meta_file = base_name + "_metadata.txt"
    with open(meta_file, "w") as f:
        f.write("МЕТАДАННЫЕ ПОЛЯРНОЙ DEM ЛУНЫ\n")
        f.write("=" * 50 + "\n\n")
        for key, value in params.items():
            f.write(f"{key}: {value}\n")
        f.write(f"\nСтатистика высот:\n")
        f.write(f"  Минимальная высота: {min_height:.1f} м\n")
        f.write(f"  Максимальная высота: {max_height:.1f} м\n")
        f.write(f"  Средняя высота: {mean_height:.1f} м\n")
        f.write(f"  Относительно сферы радиусом: {OFFSET} м\n")

    print(f"📄 Метаданные сохранены в {meta_file}")

    return elevation_meters, params


def create_coordinate_grid(params):
    """
    Создает сетку координат для полярной стереографической проекции

    Parameters:
    -----------
    params : dict
        Параметры из PDS файла

    Returns:
    --------
    grid_x, grid_y : ndarray
        Координаты X, Y в метрах от центра проекции
    """

    NROWS = params.get("lines")
    NCOLS = params.get("line_samples")
    map_scale = params.get("map_scale", 100.0)
    center_x_px = params.get("sample_projection_offset", NCOLS / 2)
    center_y_px = params.get("line_projection_offset", NROWS / 2)

    # Создаем индексы пикселей
    x_indices = np.arange(NCOLS)
    y_indices = np.arange(NROWS)

    # Преобразуем в метры от центра
    grid_x = (x_indices - center_x_px) * map_scale
    grid_y = (y_indices - center_y_px) * map_scale

    # Создаем 2D сетку
    grid_x_2d, grid_y_2d = np.meshgrid(grid_x, grid_y)

    return grid_x_2d, grid_y_2d


def convert_to_geographic(grid_x, grid_y, params):
    """
    Преобразует проекционные координаты в географические (широта/долгота)

    Parameters:
    -----------
    grid_x, grid_y : ndarray
        Координаты X, Y в метрах от центра
    params : dict
        Параметры из PDS файла

    Returns:
    --------
    lat, lon : ndarray
        Географические координаты в градусах
    """

    R = params.get("a_axis_radius", 1737.4) * 1000  # в метрах
    center_lat = params.get("center_latitude", 90.0)  # северный полюс
    center_lon = params.get("center_longitude", 0.0)

    # Для полярной стереографической проекции (сфера)
    # Формулы обратного преобразования

    # Расстояние от центра
    r = np.sqrt(grid_x**2 + grid_y**2)

    # Угол от оси X (восток)
    theta = np.arctan2(grid_y, grid_x)

    # Геометрический параметр
    chi = 2 * np.arctan(r / (2 * R))

    # Широта (для северного полюса)
    lat = 90 - np.degrees(chi)

    # Долгота
    lon = np.degrees(theta) + center_lon

    # Приводим долготу к диапазону 0-360°
    lon = lon % 360

    return lat, lon


if __name__ == "__main__":
    print("=" * 60)
    print("🛸 КОНВЕРТЕР ПОЛЯРНЫХ LDEM ДАННЫХ ЛУНЫ")
    print("=" * 60)

    download_img()

    # Пример 2: Работа с локальным файлом
    print("\n2. Обработка локального файла...")

    # Укажите имя .lbl файла
    LBL_FILE = "ldem_45n_100m.lbl"  # или другой полярный файл

    if os.path.exists(LBL_FILE):
        print(f"✅ Найден файл метаданных: {LBL_FILE}")

        # Преобразование данных
        elevation_data, params = convert_polar_ldem_to_meters(
            LBL_FILE, output_format="npz"  # или "bin", "tif"
        )

        if elevation_data is not None:
            print("\n✅ Преобразование завершено успешно!")

            # Создание координатной сетки
            print("\n3. Создание координатной сетки...")
            grid_x, grid_y = create_coordinate_grid(params)
            print(f"   Размер сетки: {grid_x.shape}")
            print(f"   Диапазон X: {grid_x.min():.0f} до {grid_x.max():.0f} м")
            print(f"   Диапазон Y: {grid_y.min():.0f} до {grid_y.max():.0f} м")

            # Пример преобразования координат
            print("\n4. Преобразование координат...")
            # Выберем несколько точек для примера
            test_points = [(0, 0), (10000, 0), (0, 10000)]

            for x, y in test_points:
                # Находим ближайшие пиксели
                px = int(
                    x / params.get("map_scale", 100.0)
                    + params.get("sample_projection_offset", 14400)
                )
                py = int(
                    y / params.get("map_scale", 100.0)
                    + params.get("line_projection_offset", 14400)
                )

                if 0 <= px < params.get("line_samples") and 0 <= py < params.get(
                    "lines"
                ):
                    height = elevation_data[py, px]
                    print(f"   Точка ({x:.0f}, {y:.0f}) м: высота = {height:.1f} м")

                    # Преобразуем в географические координаты
                    lat, lon = convert_to_geographic(
                        np.array([x]), np.array([y]), params
                    )
                    print(
                        f"     Географические координаты: {lat[0]:.2f}°N, {lon[0]:.2f}°E"
                    )

    else:
        print(f"❌ Файл {LBL_FILE} не найден!")
        print("\n📋 Примеры доступных полярных файлов:")
        print("   ldem_45n_100m.img/lbl  - северное полушарие, 100м")
        print("   ldem_45s_100m.img/lbl  - южное полушарие, 100м")
        print("   ldem_45n_020m.img/lbl  - северное полушарие, 20м")
        print("   ldem_45n_005m.img/lbl  - северное полушарие, 5м")
        print("\nℹ Скачайте файлы с сайта PDS или используйте download_polar_file()")
