import numpy as np
from datetime import datetime
import re


class IONEXParser:
    def __init__(self, filepath):
        self.filepath = filepath
        self.maps = []
        self.header = {}

    def parse(self):
        with open(self.filepath, "r") as f:
            lines = f.readlines()

        # Парсинг заголовка
        self._parse_header(lines)

        # Парсинг данных
        self._parse_data(lines)

        return self.maps, self.header

    def _parse_header(self, lines):
        for i, line in enumerate(lines):
            if "END OF HEADER" in line:
                self.header_end_line = i
                break

            # Извлекаем ключевые параметры
            if "LAT1 / LAT2 / DLAT" in line:
                lat1, lat2, dlat = map(float, line.split()[:3])
                self.header["lat_range"] = (lat1, lat2, dlat)
                self.n_lat = int((lat2 - lat1) / dlat) + 1

            elif "LON1 / LON2 / DLON" in line:
                lon1, lon2, dlon = map(float, line.split()[:3])
                self.header["lon_range"] = (lon1, lon2, dlon)
                self.n_lon = int((lon2 - lon1) / dlon) + 1

            elif "HGT1 / HGT2 / DHGT" in line:
                hgt1, hgt2, dhgt = map(float, line.split()[:3])
                self.header["height"] = hgt1

            elif "EPOCH OF FIRST MAP" in line:
                year, month, day, hour, minute, sec = map(int, line.split()[:6])
                self.header["first_epoch"] = datetime(
                    year, month, day, hour, minute, sec
                )

            elif "# OF MAPS IN FILE" in line:
                self.n_maps = int(line.split()[0])
                self.header["n_maps"] = self.n_maps

            elif "INTERVAL" in line:
                self.header["interval"] = int(line.split()[0])

    def _parse_data(self, lines):
        current_line = self.header_end_line + 1

        while current_line < len(lines):
            if "START OF TEC MAP" not in lines[current_line]:
                current_line += 1
                continue

            current_line += 1

            # Чтение времени эпохи
            epoch_data = list(map(int, lines[current_line].split()[:6]))
            epoch = datetime(*epoch_data)
            current_line += 1

            # Создание массива для карты
            tec_map = np.zeros((self.n_lat, self.n_lon))
            lat_idx = 0

            while lat_idx < self.n_lat:
                line = lines[current_line].strip()

                # Проверяем, содержит ли строка данные о широте
                # Формат: 87.5-180.0 180.0   5.0 450.0
                if (
                    line.replace(".", "", 1)
                    .replace("-", "", 1)
                    .split()[0]
                    .replace(".", "", 1)
                    .isdigit()
                ):
                    # Разделяем первую часть (например, "87.5-180.0")
                    parts = line.split()
                    first_part = parts[0]

                    # Разделяем широту и долготу (могут быть разделены знаком минус)
                    # Ищем позицию первого знака минус после цифр
                    if "-" in first_part and not first_part.startswith("-"):
                        # Случай: "87.5-180.0" - разделяем по первому минусу
                        lat_part, rest = first_part.split("-", 1)
                        lat = float(lat_part)
                    else:
                        # Случай: "-87.5-180.0" - первое число отрицательное
                        # Ищем второй минус
                        lat_part = first_part[: first_part.find("-", 1)]
                        lat = float(lat_part)

                    current_line += 1

                    # Сбор всех значений TEC для текущей широты
                    tec_values = []
                    while len(tec_values) < self.n_lon:
                        if current_line >= len(lines):
                            break
                        # Проверяем, не началась ли новая широта или новый блок
                        next_line = lines[current_line].strip()
                        if "LAT/LON1/LON2/DLON/H" in next_line:
                            break
                        if "END OF" in next_line or "START OF" in next_line:
                            break

                        # Разделяем строку на числа
                        values = re.findall(r"[-+]?\d*\.?\d+", lines[current_line])
                        if values:
                            tec_values.extend(map(float, values))
                        current_line += 1

                    if len(tec_values) == self.n_lon:
                        tec_map[lat_idx, :] = tec_values
                        lat_idx += 1
                else:
                    current_line += 1

            self.maps.append({"epoch": epoch, "tec": tec_map})

            # Пропускаем END OF TEC MAP если есть
            if current_line < len(lines) and "END OF TEC MAP" in lines[current_line]:
                current_line += 1


# Альтернативная, более простая версия парсера
def parse_ionex_simple(filepath):
    """Упрощенный парсер для файлов IONEX"""
    with open(filepath, "r") as f:
        content = f.read()

    # Разделяем на строки
    lines = content.split("\n")

    # Парсим заголовок
    header = {}
    for i, line in enumerate(lines):
        if "END OF HEADER" in line:
            data_start = i + 1
            break

        # Парсим ключевые параметры
        if "LAT1 / LAT2 / DLAT" in line:
            lat1, lat2, dlat = map(float, line.split()[:3])
            header["lat_range"] = (lat1, lat2, dlat)
            n_lat = int((lat2 - lat1) / dlat) + 1

        elif "LON1 / LON2 / DLON" in line:
            lon1, lon2, dlon = map(float, line.split()[:3])
            header["lon_range"] = (lon1, lon2, dlon)
            n_lon = int((lon2 - lon1) / dlon) + 1

        elif "# OF MAPS IN FILE" in line:
            n_maps = int(line.split()[0])
            header["n_maps"] = n_maps

    # Парсим данные
    maps = []
    i = data_start

    while i < len(lines):
        if "START OF TEC MAP" not in lines[i]:
            i += 1
            continue

        i += 1  # Пропускаем START OF TEC MAP

        # Читаем эпоху
        epoch_data = list(map(int, lines[i].split()[:6]))
        epoch = datetime(*epoch_data)
        i += 1

        # Создаем массив для карты
        tec_map = np.zeros((n_lat, n_lon))
        lat_idx = 0

        while lat_idx < n_lat and i < len(lines):
            line = lines[i].strip()

            # Пропускаем пустые строки
            if not line:
                i += 1
                continue

            # Проверяем, является ли строка строкой с данными широты
            # Ищем строки, которые начинаются с числа (широты)
            if line[0].isdigit() or (line[0] == "-" and line[1].isdigit()):
                # Разбираем первую часть чтобы получить широту
                parts = line.split()
                first_part = parts[0]

                # Обрабатываем случай, когда широта и долгота слиты
                if "-" in first_part and not first_part.startswith("-"):
                    # Формат: "87.5-180.0"
                    lat_part = first_part.split("-")[0]
                    lat = float(lat_part)
                elif first_part.count("-") > 1:
                    # Формат: "-87.5-180.0"
                    # Находим второй минус
                    first_minus = first_part.find("-")
                    second_minus = first_part.find("-", first_minus + 1)
                    lat_part = first_part[:second_minus]
                    lat = float(lat_part)
                else:
                    lat = float(first_part)

                i += 1

                # Собираем значения TEC для этой широты
                tec_values = []
                while len(tec_values) < n_lon and i < len(lines):
                    next_line = lines[i].strip()

                    # Если строка начинается с числа или минуса, это данные TEC
                    if next_line and (
                        next_line[0].isdigit()
                        or (
                            next_line[0] == "-"
                            and len(next_line) > 1
                            and next_line[1].isdigit()
                        )
                    ):
                        # Извлекаем все числа из строки
                        numbers = re.findall(r"[-+]?\d*\.?\d+", next_line)
                        tec_values.extend(map(float, numbers))
                    else:
                        # Если это не данные TEC, возможно, это следующая широта
                        break
                    i += 1

                if len(tec_values) == n_lon:
                    tec_map[lat_idx, :] = tec_values
                    lat_idx += 1
            else:
                i += 1

        maps.append({"epoch": epoch, "tec": tec_map})

        # Пропускаем END OF TEC MAP если есть
        if i < len(lines) and "END OF TEC MAP" in lines[i]:
            i += 1

    return maps, header


# Функция для визуализации
def plot_tec_map(tec_map, header, epoch=None):
    """Визуализация карты TEC"""
    lat_range = header["lat_range"]
    lon_range = header["lon_range"]

    lats = np.arange(lat_range[0], lat_range[1] + lat_range[2], lat_range[2])
    lons = np.arange(lon_range[0], lon_range[1] + lon_range[2], lon_range[2])

    plt.figure(figsize=(12, 6))
    plt.contourf(lons, lats, tec_map, levels=50, cmap="jet")
    plt.colorbar(label="TECU (10¹⁶ el/m²)")
    plt.xlabel("Долгота (°)")
    plt.ylabel("Широта (°)")

    title = "Карта вертикального общего электронного содержания (VTEC)"
    if epoch:
        title += f'\n{epoch.strftime("%Y-%m-%d %H:%M UTC")}'
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.show()


# Основная программа
if __name__ == "__main__":
    import matplotlib.pyplot as plt

    # Используем упрощенный парсер
    filepath = "IACG1820.23I"
    print(f"Парсинг файла: {filepath}")

    maps, header = parse_ionex_simple(filepath)

    print(f"Успешно прочитано карт: {len(maps)}")
    print(f"Размер каждой карты: {maps[0]['tec'].shape if maps else 'Нет данных'}")
    print(f"Диапазон широт: {header.get('lat_range', 'Не найден')}")
    print(f"Диапазон долгот: {header.get('lon_range', 'Не найден')}")

    # Выводим первую карту
    if maps:
        print(f"\nПервая эпоха: {maps[0]['epoch']}")
        print(f"TEC минимум: {maps[0]['tec'].min():.1f} TECU")
        print(f"TEC максимум: {maps[0]['tec'].max():.1f} TECU")
        print(f"TEC среднее: {maps[0]['tec'].mean():.1f} TECU")

        # Визуализируем
        plot_tec_map(maps[0]["tec"], header, maps[0]["epoch"])
