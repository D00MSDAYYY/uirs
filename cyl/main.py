import numpy as np
import os
import re
import requests


def download_img(url=None, filename="ldem_64.img", save_path=None):
    """
    Скачивает файл ldem_64.img с сайта PDS Geosciences
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


def parse_pds_label_detailed(label_file):
    """Парсит PDS .lbl файл и извлекает ВСЕ параметры данных"""
    params = {}

    try:
        with open(label_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Важно: ищем SAMPLE_TYPE для определения порядка байтов
        patterns = {
            "lines": r"LINES\s*=\s*(\d+)",
            "line_samples": r"LINE_SAMPLES\s*=\s*(\d+)",
            "scaling_factor": r"SCALING_FACTOR\s*=\s*([\d\.\-]+)",
            "offset": r"OFFSET\s*=\s*([\d\.\-]+)",
            "sample_bits": r"SAMPLE_BITS\s*=\s*(\d+)",
            "sample_type": r"SAMPLE_TYPE\s*=\s*\"([^\"]+)\"",  # Ключевой параметр!
            "file_records": r"FILE_RECORDS\s*=\s*(\d+)",
            "record_bytes": r"RECORD_BYTES\s*=\s*(\d+)",
            "map_resolution": r"MAP_RESOLUTION\s*=\s*(\d+)",
            "map_scale": r"MAP_SCALE\s*=\s*([\d\.]+)",
            "minimum": r"MINIMUM\s*=\s*([\d\.\-]+)",
            "maximum": r"MAXIMUM\s*=\s*([\d\.\-]+)",
            "center_longitude": r"CENTER_LONGITUDE\s*=\s*([\d\.]+)\s*<deg>",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    if key in [
                        "scaling_factor",
                        "offset",
                        "map_scale",
                        "minimum",
                        "maximum",
                        "center_longitude",
                    ]:
                        params[key] = float(match.group(1))
                    elif key == "sample_type":
                        params[key] = match.group(1)
                    else:
                        params[key] = int(match.group(1))
                except ValueError:
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

        print("✓ Параметры успешно извлечены из PDS файла:")
        print(f"  Порядок байтов: {params.get('sample_type', 'не указан')}")
        print(
            f"  Размер: {params.get('lines', '?')} × {params.get('line_samples', '?')}"
        )
        print(f"  Scaling factor: {params.get('scaling_factor', '?')}")
        print(f"  Offset: {params.get('offset', '?')}")
        print(f"  Центр долготы: {params.get('center_longitude', 180.0)}°")

        return params

    except Exception as e:
        print(f"✗ Ошибка чтения PDS файла: {e}")
        return None


def convert_ldem_to_meters_corrected(label_file):
    """ПРАВИЛЬНОЕ преобразование LDEM данных с учетом порядка байтов"""
    params = parse_pds_label_detailed(label_file)
    if not params:
        return None

    # Основные параметры
    SCALING_FACTOR = params.get("scaling_factor", 0.5)
    OFFSET = params.get("offset", 1737400.0)
    NROWS = params.get("lines", 11520)
    NCOLS = params.get("line_samples", 23040)
    SAMPLE_BITS = params.get("sample_bits", 16)
    SAMPLE_TYPE = params.get("sample_type", "LSB_INTEGER")
    input_file = params.get("file_name", "ldem_64.img")

    output_file = "ldem_64_meters_corrected.dat"

    # Проверяем существование файла
    if not os.path.exists(input_file):
        print(f"✗ Ошибка: файл {input_file} не найден!")
        return None

    print(f"\n📊 Начинаем преобразование {input_file}...")
    print(f"   Размер: {NCOLS} × {NROWS} пикселей")
    print(f"   Порядок байтов: {SAMPLE_TYPE}")
    print(f"   Формула: высота = данные × {SCALING_FACTOR}")

    # Определяем тип данных на основе sample_bits и порядка байтов
    if SAMPLE_BITS == 16:
        if "LSB" in SAMPLE_TYPE.upper():  # Little-endian
            dtype = "<i2"  # little-endian int16
            print("  Используем little-endian int16")
        else:  # Big-endian или MSB
            dtype = ">i2"  # big-endian int16
            print("  Используем big-endian int16")
    else:
        dtype = ">i4"  # по умолчанию big-endian int32

    # Читаем бинарные данные
    print("📥 Чтение данных...")
    try:
        with open(input_file, "rb") as f:
            data = np.fromfile(f, dtype=dtype)
    except Exception as e:
        print(f"✗ Ошибка чтения файла: {e}")
        # Пробуем альтернативный порядок байтов
        print("ℹ Пробую альтернативный порядок байтов...")
        try:
            if dtype == "<i2":
                alt_dtype = ">i2"
            else:
                alt_dtype = "<i2"

            with open(input_file, "rb") as f:
                data = np.fromfile(f, dtype=alt_dtype)
            print(f"✓ Успешно с {alt_dtype}")
        except Exception as e2:
            print(f"✗ Ошибка с альтернативным порядком: {e2}")
            return None

    # Проверяем размер данных
    expected_size = NCOLS * NROWS
    if len(data) != expected_size:
        print(
            f"⚠ Предупреждение: ожидалось {expected_size} значений, получено {len(data)}"
        )
        # Обрезаем до ожидаемого размера
        if len(data) > expected_size:
            data = data[:expected_size]
            print(f"ℹ Обрезано до {expected_size} значений")
        else:
            print(f"ℹ Файл меньше ожидаемого, возможно поврежден")
            return None

    # Изменяем форму массива
    data = data.reshape(NROWS, NCOLS)

    # Преобразование в метры
    print("🔄 Преобразование в метры...")
    elevation_meters = data.astype(np.float32) * SCALING_FACTOR

    # Проверяем диапазон значений
    min_val = np.nanmin(elevation_meters)
    max_val = np.nanmax(elevation_meters)
    mean_val = np.nanmean(elevation_meters)

    print(f"📈 Проверка диапазона:")
    print(f"   Минимум: {min_val:.1f} м")
    print(f"   Максимум: {max_val:.1f} м")
    print(f"   Среднее: {mean_val:.1f} м")

    # Проверяем на реалистичность
    if min_val < -10000 or max_val > 10000:
        print(f"⚠ Внимание: значения вне реалистичного диапазона для Луны!")
        print(f"   Ожидается: -9000...+9000 м")
        print(f"   Получено: {min_val:.0f}...+{max_val:.0f} м")
        print(f"   Возможно неверный порядок байтов или scaling factor")

    # Сохраняем результат
    print("💾 Сохранение результата...")
    elevation_meters.astype(np.float32).tofile(output_file)

    # Сохраняем параметры для использования
    params_file = "ldem_64_params_corrected.npy"
    np.save(params_file, params)
    print(f"✓ Параметры сохранены в {params_file}")
    print(f"✓ Высоты сохранены в {output_file}")

    return params


class CylindricalLunarDEMCorrected:
    """Исправленный класс для работы с цилиндрической DEM Луны"""

    def __init__(
        self,
        data_file="ldem_64_meters_corrected.dat",
        params_file="ldem_64_params_corrected.npy",
    ):
        """
        Инициализация DEM с исправленными параметрами
        """
        self.data_file = data_file
        self.params_file = params_file
        self.load_data()

    def load_data(self):
        """Загружает данные и параметры"""
        # Загружаем параметры
        if os.path.exists(self.params_file):
            self.params = np.load(self.params_file, allow_pickle=True).item()
            print("✓ Параметры загружены")
        else:
            print("⚠ Файл параметров не найден, используем значения по умолчанию")
            self.params = {
                "lines": 11520,
                "line_samples": 23040,
                "scaling_factor": 0.5,
                "offset": 1737400.0,
                "map_resolution": 64,
                "map_scale": 473.802,
                "center_longitude": 180.0,
            }

        self.LINES = self.params["lines"]
        self.LINE_SAMPLES = self.params["line_samples"]
        self.SCALING_FACTOR = self.params.get("scaling_factor", 0.5)
        self.OFFSET = self.params.get("offset", 1737400.0)
        self.CENTER_LON = self.params.get("center_longitude", 180.0)

        # Загружаем данные высот
        print(f"📂 Загрузка данных высот из {self.data_file}...")

        try:
            self.elevation_data = np.fromfile(self.data_file, dtype=np.float32)
        except:
            print("❌ Ошибка загрузки данных. Убедитесь, что файл существует.")
            print(
                "   Запустите сначала: convert_ldem_to_meters_corrected('ldem_64.lbl')"
            )
            return False

        # Проверяем размер
        expected_size = self.LINES * self.LINE_SAMPLES
        if len(self.elevation_data) != expected_size:
            print(
                f"⚠ Предупреждение: ожидалось {expected_size} значений, получено {len(self.elevation_data)}"
            )
            return False

        # Изменяем форму
        self.elevation_data = self.elevation_data.reshape(self.LINES, self.LINE_SAMPLES)
        print(f"✅ Данные загружены: {self.LINE_SAMPLES}x{self.LINES} пикселей")

        # Вычисляем статистику
        self.min_height = np.nanmin(self.elevation_data)
        self.max_height = np.nanmax(self.elevation_data)
        self.mean_height = np.nanmean(self.elevation_data)

        print(f"📊 Статистика высот:")
        print(f"   Минимум: {self.min_height:.1f} м")
        print(f"   Максимум: {self.max_height:.1f} м")
        print(f"   Среднее: {self.mean_height:.1f} м")

        # Проверяем на реалистичность
        if self.min_height < -9000 or self.max_height > 9000:
            print("⚠ Внимание: значения могут быть некорректными!")

        return True

    def parse_coordinates(self, input_str):
        """
        Парсит строку с координатами
        """
        try:
            parts = input_str.lower().split()
            if len(parts) != 2:
                raise ValueError("Неверный формат. Используйте: n50 w70")

            # Парсим широту
            lat_str = parts[0]
            if lat_str.startswith("n"):
                latitude = float(lat_str[1:])
            elif lat_str.startswith("s"):
                latitude = -float(lat_str[1:])
            else:
                raise ValueError("Широта должна начинаться с 'n' или 's'")

            # Парсим долготу
            lon_str = parts[1]
            if lon_str.startswith("w"):
                longitude = -float(lon_str[1:])
            elif lon_str.startswith("e"):
                longitude = float(lon_str[1:])
            else:
                raise ValueError("Долгота должна начинаться с 'w' или 'e'")

            return latitude, longitude

        except ValueError as e:
            print(f"❌ Ошибка: {e}")
            return None, None

    def coordinates_to_pixel_simple(self, lat, lon):
        """
        Простое преобразование координат в пиксели
        (без учета центра на 180° для тестирования)
        """
        # Проверяем границы
        if lat < -90 or lat > 90:
            print(f"❌ Широта {lat}° вне диапазона")
            return None, None

        # Нормализуем долготу 0-360
        lon_norm = lon % 360

        # Упрощенная версия: долгота 0° = левый край
        # Широта +90° (север) = верхний край
        lat_ratio = (90.0 - lat) / 180.0
        y_pixel = lat_ratio * (self.LINES - 1)

        lon_ratio = lon_norm / 360.0
        x_pixel = lon_ratio * (self.LINE_SAMPLES - 1)

        # Ограничиваем
        x = int(np.clip(x_pixel, 0, self.LINE_SAMPLES - 1))
        y = int(np.clip(y_pixel, 0, self.LINES - 1))

        return x, y

    def coordinates_to_pixel_with_center(self, lat, lon):
        """
        Преобразование с учетом центра на 180° долготы
        """
        if lat < -90 or lat > 90:
            return None, None

        # Нормализуем долготу 0-360
        lon_norm = lon % 360

        # С учетом центра на 180°
        # Долгота 180° должна быть в центре изображения
        lon_shifted = (lon_norm + 180) % 360

        lat_ratio = (90.0 - lat) / 180.0
        y_pixel = lat_ratio * (self.LINES - 1)

        lon_ratio = lon_shifted / 360.0
        x_pixel = lon_ratio * (self.LINE_SAMPLES - 1)

        x = int(np.clip(x_pixel, 0, self.LINE_SAMPLES - 1))
        y = int(np.clip(y_pixel, 0, self.LINES - 1))

        return x, y

    def get_elevation(self, x, y):
        """Получает высоту в пиксельных координатах"""
        if x < 0 or x >= self.LINE_SAMPLES or y < 0 or y >= self.LINES:
            return None

        # Ближайший пиксель
        height = self.elevation_data[y, x]
        return float(height)

    def test_coordinates(self, test_points):
        """Тестирование нескольких известных точек"""
        print("\n🧪 ТЕСТИРОВАНИЕ КООРДИНАТ:")
        print("-" * 70)

        for name, lat, lon in test_points:
            # Пробуем оба метода
            x1, y1 = self.coordinates_to_pixel_simple(lat, lon)
            x2, y2 = self.coordinates_to_pixel_with_center(lat, lon)

            height1 = self.get_elevation(x1, y1) if x1 is not None else None
            height2 = self.get_elevation(x2, y2) if x2 is not None else None

            print(f"\n📍 {name}:")
            print(f"   Координаты: {lat}°N, {lon}°E")
            print(f"   Метод 1 (простой): пиксель ({x1}, {y1}) = {height1:.1f} м")
            print(f"   Метод 2 (с центром): пиксель ({x2}, {y2}) = {height2:.1f} м")

    def interactive_mode(self):
        """Интерактивный режим"""
        print("\n" + "=" * 60)
        print("🎯 ИНТЕРАКТИВНЫЙ РЕЖИМ ПОИСКА ВЫСОТ")
        print("=" * 60)
        print("\nТестируйте оба метода преобразования координат")
        print("Формат: n50 w70  или  s30 e45")
        print("Команды: 'q' - выход, 't' - тест, 's' - статистика")

        while True:
            try:
                user_input = input("\nВведите координаты: ").strip()

                if user_input.lower() == "q":
                    break

                if user_input.lower() == "t":
                    # Тестовые точки
                    test_points = [
                        ("Северный полюс", 90, 0),
                        ("Южный полюс", -90, 0),
                        ("Экватор 0°", 0, 0),
                        ("Экватор 180°", 0, 180),
                        ("n50 w70", 50, -70),
                    ]
                    self.test_coordinates(test_points)
                    continue

                if user_input.lower() == "s":
                    print(f"\n📊 Статистика:")
                    print(f"   Минимум: {self.min_height:.1f} м")
                    print(f"   Максимум: {self.max_height:.1f} м")
                    print(f"   Среднее: {self.mean_height:.1f} м")
                    continue

                # Парсим координаты
                lat, lon = self.parse_coordinates(user_input)
                if lat is None:
                    continue

                print(f"\n📍 Координаты: {lat:.4f}°, {lon:.4f}°")

                # Метод 1: простой
                x1, y1 = self.coordinates_to_pixel_simple(lat, lon)
                if x1 is not None:
                    h1 = self.get_elevation(x1, y1)
                    print(f"📏 Метод 1 (простой): {h1:.2f} м")

                # Метод 2: с центром
                x2, y2 = self.coordinates_to_pixel_with_center(lat, lon)
                if x2 is not None:
                    h2 = self.get_elevation(x2, y2)
                    print(f"📏 Метод 2 (с центром): {h2:.2f} м")

                print("-" * 40)

            except KeyboardInterrupt:
                print("\n\nПрервано")
                break
            except Exception as e:
                print(f"❌ Ошибка: {e}")


# Основная программа
if __name__ == "__main__":
    print("=" * 70)
    print("🌕 ИСПРАВЛЕННЫЙ КОНВЕРТЕР ЦИЛИНДРИЧЕСКОЙ DEM ЛУНЫ")
    print("=" * 70)

    # Проверяем наличие файлов
    img_file = "ldem_64.img"
    lbl_file = "ldem_64.lbl"

    if not os.path.exists(img_file) or not os.path.exists(lbl_file):
        print("❌ Не найдены необходимые файлы")
        print("1. Скачиваем файлы...")
        download_img()
        print("\n2. Убедитесь, что файл ldem_64.lbl также скачан")
        print("   (обычно автоматически скачивается браузером)")
    else:
        print("✓ Файлы ldem_64.img и ldem_64.lbl найдены")

    print("\n3. Конвертируем данные с правильным порядком байтов...")
    params = convert_ldem_to_meters_corrected(lbl_file)

    if params:
        print("\n4. Загружаем исправленные данные...")
        dem = CylindricalLunarDEMCorrected()
        if dem.load_data():
            dem.interactive_mode()
    else:
        print("❌ Конвертация не удалась")
