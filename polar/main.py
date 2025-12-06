import numpy as np
import os
import warnings

warnings.filterwarnings("ignore")


class LunarDEMHeightFinder:
    """Класс для поиска высот по координатам из NPZ файла"""

    def __init__(self, npz_file):
        """
        Инициализация

        Parameters:
        -----------
        npz_file : str
            Путь к NPZ файлу с данными DEM
        """
        self.npz_file = npz_file
        self.load_data()

    def load_data(self):
        """Загружает данные из NPZ файла"""
        try:
            print(f"📂 Загрузка данных из {self.npz_file}...")

            # Загружаем данные
            data = np.load(self.npz_file, allow_pickle=True)

            # Проверяем наличие необходимых массивов
            if "elevation" in data:
                self.elevation = data["elevation"]
                print(
                    f"✅ Загружены высоты: {self.elevation.shape[1]}x{self.elevation.shape[0]} пикселей"
                )
            else:
                raise ValueError("Файл не содержит массива 'elevation'")

            if "metadata" in data:
                self.metadata = data["metadata"].item()
                print(f"✅ Загружены метаданные")
            else:
                self.metadata = {}
                print("⚠ Метаданные не найдены")

            # Выводим основную информацию
            if self.metadata:
                print(f"\n📋 Основная информация:")
                print(f"   Проекция: {self.metadata.get('map_projection_type', 'N/A')}")
                print(
                    f"   Разрешение: {self.metadata.get('map_scale', 'N/A')} м/пиксель"
                )
                print(
                    f"   Охват широт: {self.metadata.get('minimum_latitude', 'N/A')}° - {self.metadata.get('maximum_latitude', 'N/A')}°"
                )
                print(
                    f"   Центр: {self.metadata.get('center_latitude', 'N/A')}°, {self.metadata.get('center_longitude', 'N/A')}°"
                )

        except Exception as e:
            print(f"❌ Ошибка загрузки данных: {e}")
            raise

    def latlon_to_pixel(self, lat, lon):
        """
        Преобразует географические координаты в пиксельные
        """
        # Проверяем наличие необходимых параметров
        required_params = [
            "map_scale",
            "sample_projection_offset",
            "line_projection_offset",
            "center_latitude",
            "center_longitude",
            "a_axis_radius",
        ]

        for param in required_params:
            if param not in self.metadata:
                print(f"❌ Отсутствует параметр: {param}")
                return None, None

        # Проверяем границы широты
        min_lat = self.metadata.get("minimum_latitude", 45)
        max_lat = self.metadata.get("maximum_latitude", 90)

        if lat < min_lat or lat > max_lat:
            print(f"❌ Широта {lat}° вне диапазона ({min_lat}° - {max_lat}°)")
            return None, None

        # Параметры проекции
        R = self.metadata["a_axis_radius"] * 1000  # в метрах
        map_scale = self.metadata["map_scale"]
        center_x_px = self.metadata["sample_projection_offset"]
        center_y_px = self.metadata["line_projection_offset"]
        center_lon = self.metadata.get("center_longitude", 0)

        # Преобразование в полярные стереографические координаты
        chi = np.radians(90 - lat)  # угол от полюса
        r = 2 * R * np.tan(chi / 2)  # расстояние от центра

        theta = np.radians(lon - center_lon)  # азимут

        # Координаты в метрах
        x = r * np.cos(theta)
        y = r * np.sin(theta)

        # Координаты в пикселях
        px = x / map_scale + center_x_px
        py = y / map_scale + center_y_px

        return px, py

    def get_height_at_latlon(self, lat, lon):
        """
        Получает высоту в заданных географических координатах

        Returns:
        --------
        height : float или None
            Высота в метрах, или None если ошибка
        """
        # Преобразуем в пиксельные координаты
        px, py = self.latlon_to_pixel(lat, lon)

        if px is None or py is None:
            return None

        # Проверяем границы
        nrows, ncols = self.elevation.shape

        if px < 0 or px >= ncols or py < 0 or py >= nrows:
            print(f"❌ Координаты вне границ данных")
            return None

        # Ближайший пиксель (без интерполяции для скорости)
        x = int(np.round(px))
        y = int(np.round(py))

        height = self.elevation[y, x]

        return height

    def get_height_interpolated(self, lat, lon):
        """
        Получает высоту с билинейной интерполяцией
        """
        px, py = self.latlon_to_pixel(lat, lon)

        if px is None or py is None:
            return None

        nrows, ncols = self.elevation.shape

        if px < 0 or px >= ncols or py < 0 or py >= nrows:
            return None

        # Билинейная интерполяция
        x1 = int(np.floor(px))
        x2 = int(np.ceil(px))
        y1 = int(np.floor(py))
        y2 = int(np.ceil(py))

        # Проверяем границы
        x1 = max(0, min(x1, ncols - 1))
        x2 = max(0, min(x2, ncols - 1))
        y1 = max(0, min(y1, nrows - 1))
        y2 = max(0, min(y2, nrows - 1))

        # Значения в соседних пикселях
        v11 = self.elevation[y1, x1]
        v12 = self.elevation[y1, x2]
        v21 = self.elevation[y2, x1]
        v22 = self.elevation[y2, x2]

        # Веса интерполяции
        wx = px - x1
        wy = py - y1

        # Интерполяция
        height = (
            (1 - wx) * (1 - wy) * v11
            + wx * (1 - wy) * v12
            + (1 - wx) * wy * v21
            + wx * wy * v22
        )

        return height


def print_welcome():
    """Выводит приветственное сообщение"""
    print("=" * 70)
    print("🌕 ПОИСК ВЫСОТ НА ЛУНЕ ПО КООРДИНАТАМ")
    print("=" * 70)
    print("\nЭтот инструмент позволяет найти высоту поверхности Луны")
    print("в любой точке северного полярного региона (45°-90°N).")
    print("\nФормат ввода: широта, долгота (например: 85.5, 45.2)")
    print("Долгота: 0-360°, где 0° = центральный меридиан")
    print("\nКоманды: 'q' - выход, 'h' - справка, 's' - статистика")
    print("=" * 70)


def print_help():
    """Выводит справку"""
    help_text = """
📖 СПРАВКА:

ФОРМАТ ВВОДА:
  • Введите широту и долготу через запятую
  • Пример: 85.5, 45.2
  • Широта должна быть от 45° до 90° (северное полушарие)
  • Долгота может быть от 0° до 360°

КОМАНДЫ:
  q - выход из программы
  h - показать эту справку
  s - показать статистику данных
  i - использовать интерполяцию (вкл/выкл)

ПРИМЕРЫ КООРДИНАТ:
  89.0, 0.0     - почти северный полюс
  85.0, 45.0    - район кратера Пласкетт
  75.0, 30.0    - район моря Холода
  60.0, 0.0     - граница региона
  45.0, 180.0   - южная граница данных

ВЫВОД:
  • Высота в метрах относительно сферы 1737.4 км
  • Отрицательные значения = ниже среднего уровня
  • Положительные значения = выше среднего уровня
"""
    print(help_text)


def find_npz_files():
    """Ищет NPZ файлы в текущей директории"""
    npz_files = [f for f in os.listdir(".") if f.endswith(".npz")]

    if not npz_files:
        print("❌ Не найдено NPZ файлов в текущей директории")
        print("\nСоздайте NPZ файл с помощью:")
        print("convert_polar_ldem_to_meters('ldem_45n_100m.lbl', 'npz')")
        return None

    print(f"\n📁 Найдено {len(npz_files)} NPZ файл(ов):")
    for i, file in enumerate(npz_files, 1):
        print(f"  {i}. {file}")

    if len(npz_files) == 1:
        return npz_files[0]

    try:
        choice = int(input(f"\nВыберите файл (1-{len(npz_files)}): "))
        if 1 <= choice <= len(npz_files):
            return npz_files[choice - 1]
        else:
            print("❌ Неверный выбор")
            return None
    except ValueError:
        print("❌ Введите число")
        return None


def main():
    """Основная функция"""
    print_welcome()

    # Поиск файла
    npz_file = find_npz_files()
    if not npz_file:
        return

    print(f"\n📂 Загрузка файла: {npz_file}")

    try:
        # Создаем объект для поиска высот
        height_finder = LunarDEMHeightFinder(npz_file)

        # Настройки
        use_interpolation = False

        # Основной цикл
        while True:
            print(f"\n{'─'*50}")
            print(
                f"Режим: {'с интерполяцией' if use_interpolation else 'ближайший пиксель'}"
            )
            user_input = input("\nВведите координаты или команду: ").strip()

            # Проверка команд
            if user_input.lower() == "q":
                print("Выход из программы")
                break

            if user_input.lower() == "h":
                print_help()
                continue

            if user_input.lower() == "s":
                if (
                    hasattr(height_finder, "elevation")
                    and height_finder.elevation is not None
                ):
                    data = height_finder.elevation[~np.isnan(height_finder.elevation)]
                    print(f"\n📊 Статистика высот:")
                    print(f"   Минимум: {np.min(data):.1f} м")
                    print(f"   Максимум: {np.max(data):.1f} м")
                    print(f"   Среднее: {np.mean(data):.1f} м")
                    print(f"   Стандартное отклонение: {np.std(data):.1f} м")
                continue

            if user_input.lower() == "i":
                use_interpolation = not use_interpolation
                print(
                    f"Интерполяция {'включена' if use_interpolation else 'выключена'}"
                )
                continue

            # Парсим координаты
            try:
                parts = [p.strip() for p in user_input.split(",")]
                if len(parts) != 2:
                    print("❌ Ошибка: введите две координаты через запятую")
                    continue

                lat = float(parts[0])
                lon = float(parts[1])

                # Проверяем широту
                if lat < 45 or lat > 90:
                    print(f"⚠ Внимание: широта {lat}° может быть вне диапазона данных")
                    print("   (данные обычно для 45°-90°N)")

                # Нормализуем долготу
                lon = lon % 360

                # Получаем высоту
                if use_interpolation:
                    height = height_finder.get_height_interpolated(lat, lon)
                    method = "с интерполяцией"
                else:
                    height = height_finder.get_height_at_latlon(lat, lon)
                    method = "ближайший пиксель"

                if height is None:
                    print("❌ Не удалось получить высоту для указанных координат")
                    continue

                # Выводим результат
                print(f"\n{'═'*50}")
                print(f"📍 КООРДИНАТЫ: {lat:.6f}°N, {lon:.6f}°E")
                print(f"{'═'*50}")
                print(f"📏 ВЫСОТА: {height:.2f} метров")
                print(f"   (относительно сферы 1737.4 км)")
                print(f"   Метод: {method}")

                # Абсолютный радиус
                offset = height_finder.metadata.get("offset", 1737400.0)
                radius = height + offset
                print(f"📐 АБСОЛЮТНЫЙ РАДИУС: {radius:.2f} метров")
                print(f"   (от центра Луны)")

                # Интерпретация
                print(f"\n📊 ИНТЕРПРЕТАЦИЯ:")
                if height < -4000:
                    print(f"   ⬇️  Очень низкая: глубокий кратер или бассейн")
                elif height < -2000:
                    print(f"   ⬇️  Низкая: кратер или низменность")
                elif height < -500:
                    print(f"   ⬇️  Ниже среднего")
                elif height < 500:
                    print(f"   ↔️  Около среднего уровня")
                elif height < 2000:
                    print(f"   ⬆️  Выше среднего")
                elif height < 4000:
                    print(f"   ⬆️  Высокая: горы или вал кратера")
                else:
                    print(f"   ⬆️  Очень высокая: горный пик")

                print(f"{'═'*50}")

            except ValueError:
                print("❌ Ошибка: координаты должны быть числами")
            except Exception as e:
                print(f"❌ Ошибка: {e}")

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        print("Проверьте, что файл содержит корректные данные.")


def quick_mode(npz_file, lat, lon):
    """
    Быстрый режим для получения высоты по координатам

    Parameters:
    -----------
    npz_file : str
        Путь к NPZ файлу
    lat, lon : float
        Координаты
    """
    try:
        height_finder = LunarDEMHeightFinder(npz_file)
        height = height_finder.get_height_at_latlon(lat, lon)

        if height is not None:
            print(f"\n📍 Координаты: {lat}°N, {lon}°E")
            print(f"📏 Высота: {height:.2f} м")
            offset = height_finder.metadata.get("offset", 1737400.0)
            print(f"📐 Абсолютный радиус: {height + offset:.2f} м")
        else:
            print("❌ Не удалось получить высоту")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    import sys

    # Проверяем аргументы командной строки
    if len(sys.argv) == 4:
        # Режим командной строки: python script.py файл.npz lat lon
        npz_file = sys.argv[1]
        lat = float(sys.argv[2])
        lon = float(sys.argv[3])
        quick_mode(npz_file, lat, lon)
    else:
        # Интерактивный режим
        main()
