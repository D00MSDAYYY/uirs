import numpy as np
from datetime import datetime, timedelta
import re
import matplotlib.pyplot as plt
from math import sin, cos, asin, atan2, sqrt, radians, degrees


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


def parse_glonass_nav(filepath):
    """Парсинг файла навигации ГЛОНАСС RINEX версии 2.xx"""
    satellites = {}

    with open(filepath, "r") as f:
        lines = f.readlines()

    i = 0
    # Пропускаем заголовок
    while i < len(lines) and "END OF HEADER" not in lines[i]:
        i += 1

    i += 1  # Переходим к данным после заголовка

    def parse_float(value_str):
        """Парсит числа в формате D или обычные float"""
        if isinstance(value_str, (int, float)):
            return float(value_str)

        value_str = str(value_str).strip()
        if not value_str:
            return 0.0

        try:
            # Пробуем сначала обычный float
            return float(value_str)
        except:
            try:
                # Пробуем формат D
                if "D" in value_str.upper():
                    num_part, exp_part = value_str.upper().split("D")
                    return float(num_part) * (10 ** float(exp_part))
            except:
                return 0.0

        return 0.0

    def split_scientific_numbers(line):
        """Разделяет строку с числами в научной нотации, которые могут быть слитными"""
        if not line:
            return []

        parts = []
        current = ""
        i = 0

        while i < len(line):
            char = line[i]

            # Начинаем новое число, если:
            # 1. Это начало строки ИЛИ
            # 2. Предыдущий символ был пробелом И текущий не пробел
            if i == 0 or (line[i - 1] in " \t" and char not in " \t"):
                # Собираем все символы до следующего пробела
                j = i
                while j < len(line) and line[j] not in " \t":
                    current += line[j]
                    j += 1

                if current:
                    parts.append(current)
                    current = ""

                i = j  # Пропускаем обработанные символы
            else:
                i += 1

        return parts

    def parse_data_line(line):
        """Парсит строку с данными координат/скоростей ГЛОНАСС"""
        # Сначала пробуем обычный split
        parts = line.split()
        if len(parts) >= 4:
            return parts

        # Если split дал мало частей, значит числа слитные
        # Ищем паттерны чисел в научной нотации
        import re

        # Паттерн для чисел в формате D: [+-]?\d+\.?\d*D[+-]\d+
        pattern = r"[+-]?\d+\.?\d*D[+-]\d+"
        matches = re.findall(pattern, line)

        if matches:
            return matches

        # Пробуем альтернативный метод
        parts = []
        i = 0
        while i < len(line):
            if line[i] in "+-" or line[i].isdigit() or line[i] == ".":
                # Нашли начало числа
                j = i
                while j < len(line) and (line[j].isdigit() or line[j] in "+-.Dd"):
                    j += 1
                num_str = line[i:j]
                if num_str:
                    parts.append(num_str)
                i = j
            else:
                i += 1

        return parts

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Первая строка обычно хорошо разделена пробелами
        parts = line.split()

        # Проверяем, является ли строка началом записи спутника
        # Формат: PRN год месяц день час минута секунда tau_n gamma_n t_k
        if len(parts) >= 10 and parts[0].isdigit():
            try:
                # Извлекаем базовую информацию
                prn = int(parts[0])
                year = (
                    2000 + int(parts[1]) if int(parts[1]) < 80 else 1900 + int(parts[1])
                )
                month = int(parts[2])
                day = int(parts[3])
                hour = int(parts[4])
                minute = int(parts[5])
                second = float(parts[6])

                # Проверяем, что следующие 3 строки существуют
                if i + 3 >= len(lines):
                    i += 1
                    continue

                # Парсим следующие 3 строки
                line2 = lines[i + 1].strip()
                line3 = lines[i + 2].strip()
                line4 = lines[i + 3].strip()

                line2_parts = parse_data_line(line2)
                line3_parts = parse_data_line(line3)
                line4_parts = parse_data_line(line4)

                # Отладочный вывод первых нескольких записей
                if i < 20:  # Только для первых записей
                    print(f"\nПарсинг спутника R{prn:02d} на строке {i+1}:")
                    print(f"  Строка 1: {line}")
                    print(f"  Строка 2: {line2} -> части: {line2_parts}")
                    print(f"  Строка 3: {line3} -> части: {line3_parts}")
                    print(f"  Строка 4: {line4} -> части: {line4_parts}")

                # Извлекаем данные с безопасными проверками
                X = parse_float(line2_parts[0]) if len(line2_parts) > 0 else 0.0
                Vx = parse_float(line2_parts[1]) if len(line2_parts) > 1 else 0.0

                Y = parse_float(line3_parts[0]) if len(line3_parts) > 0 else 0.0
                Vy = parse_float(line3_parts[1]) if len(line3_parts) > 1 else 0.0

                Z = parse_float(line4_parts[0]) if len(line4_parts) > 0 else 0.0
                Vz = parse_float(line4_parts[1]) if len(line4_parts) > 1 else 0.0

                # Дополнительные параметры
                frequency_channel = 0
                if len(line2_parts) > 3:
                    try:
                        freq_val = parse_float(line2_parts[3])
                        frequency_channel = int(round(freq_val))
                    except:
                        frequency_channel = 0

                health = 0
                if len(line3_parts) > 3:
                    try:
                        health_val = parse_float(line3_parts[3])
                        health = int(round(health_val))
                    except:
                        health = 0

                # Преобразуем декартовы координаты в географические
                a = 6378136.0  # большая полуось ПЗ-90 (м)
                f = 1 / 298.25784  # сжатие

                # Переводим координаты из км в метры
                X_m = X * 1000.0
                Y_m = Y * 1000.0
                Z_m = Z * 1000.0

                # Рассчитываем геодезические координаты
                e2 = 2 * f - f * f
                p = np.sqrt(X_m * X_m + Y_m * Y_m)

                if p > 0:
                    # Итерационный метод
                    lat = np.arctan2(Z_m, p * (1 - e2))

                    for _ in range(10):
                        N = a / np.sqrt(1 - e2 * np.sin(lat) ** 2)
                        h = p / np.cos(lat) - N
                        lat_new = np.arctan2(Z_m / p, 1 - e2 * N / (N + h))

                        if np.abs(lat_new - lat) < 1e-12:
                            break
                        lat = lat_new

                    N = a / np.sqrt(1 - e2 * np.sin(lat) ** 2)
                    h = p / np.cos(lat) - N
                    lon = np.arctan2(Y_m, X_m)

                    # Преобразуем в градусы
                    lat_deg = np.degrees(lat)
                    lon_deg = np.degrees(lon)

                    # Нормализуем долготу
                    if lon_deg > 180:
                        lon_deg -= 360
                    elif lon_deg < -180:
                        lon_deg += 360
                else:
                    lat_deg = 0.0
                    lon_deg = 0.0
                    h = 0.0

                # Создаем объект с данными спутника
                sat_data = {
                    "epoch": datetime(year, month, day, hour, minute, int(second)),
                    "X": X,
                    "Y": Y,
                    "Z": Z,
                    "Vx": Vx,
                    "Vy": Vy,
                    "Vz": Vz,
                    "lat": lat_deg,
                    "lon": lon_deg,
                    "height": h / 1000.0 if p > 0 else 0.0,
                    "frequency_channel": frequency_channel,
                    "health": health,
                    "tau_n": parse_float(parts[7]) if len(parts) > 7 else 0.0,
                    "gamma_n": parse_float(parts[8]) if len(parts) > 8 else 0.0,
                    "t_k": parse_float(parts[9]) if len(parts) > 9 else 0.0,
                }

                # Добавляем данные спутника
                if prn not in satellites:
                    satellites[prn] = []
                satellites[prn].append(sat_data)

                # Переходим к следующему спутнику
                i += 4

            except Exception as e:
                print(f"\nОшибка парсинга строки {i+1}: {e}")
                print(f"Строка 1: {line}")
                print(f"Строка 2: {lines[i+1].strip() if i+1 < len(lines) else 'НЕТ'}")
                print(f"Строка 3: {lines[i+2].strip() if i+2 < len(lines) else 'НЕТ'}")
                print(f"Строка 4: {lines[i+3].strip() if i+3 < len(lines) else 'НЕТ'}")
                i += 1
        else:
            i += 1

    # Сортируем данные по времени для каждого спутника
    for prn in satellites:
        satellites[prn].sort(key=lambda x: x["epoch"])

    print(f"\n{'='*60}")
    print(f"РЕЗУЛЬТАТЫ ПАРСИНГА:")
    print(f"{'='*60}")
    print(f"Успешно прочитано спутников: {len(satellites)}")

    if satellites:
        print(f"Доступные спутники: {sorted(list(satellites.keys()))}")

        # Статистика по первым 5 спутникам
        print(f"\nДетальная информация (первые 5 спутников):")
        for prn in sorted(list(satellites.keys()))[:5]:
            data = satellites[prn]
            if data:
                print(f"  Спутник R{prn:02d}:")
                print(f"    Количество записей: {len(data)}")
                print(
                    f"    Временной диапазон: {data[0]['epoch'].strftime('%H:%M:%S')} - {data[-1]['epoch'].strftime('%H:%M:%S')}"
                )
                print(
                    f"    Первая позиция: {data[0]['lat']:.2f}°N, {data[0]['lon']:.2f}°E, высота: {data[0]['height']:.0f} км"
                )
    else:
        print("ВНИМАНИЕ: Не удалось прочитать данные спутников!")
        print("Возможные причины:")
        print("  1. Неправильный формат файла")
        print("  2. Файл поврежден")
        print("  3. Проблемы с кодировкой")

    return satellites


def calculate_satellite_ground_track(satellite_data, num_points=100):
    """Рассчитывает наземную трассу спутника"""
    ground_track = []

    if not satellite_data:
        return ground_track

    # Для простоты используем линейную интерполяцию между точками
    for i in range(len(satellite_data) - 1):
        point1 = satellite_data[i]
        point2 = satellite_data[i + 1]

        # Интерполируем между двумя точками
        for j in range(num_points):
            t = j / num_points
            lat = point1["lat"] + t * (point2["lat"] - point1["lat"])
            lon = point1["lon"] + t * (point2["lon"] - point1["lon"])

            # Корректируем долготу для непрерывности
            if abs(point2["lon"] - point1["lon"]) > 180:
                if point1["lon"] < 0:
                    lon = point1["lon"] + t * ((point2["lon"] + 360) - point1["lon"])
                else:
                    lon = point1["lon"] + t * ((point2["lon"] - 360) - point1["lon"])

            if lon > 180:
                lon -= 360
            elif lon < -180:
                lon += 360

            ground_track.append((lon, lat))

    return ground_track


def plot_tec_map_with_satellites(
    tec_map, header, epoch, satellites_data, selected_prns=[1, 2, 3]
):
    """Визуализация карты TEC с траекториями спутников (только 2D карта)"""
    lat_range = header["lat_range"]
    lon_range = header["lon_range"]

    lats = np.arange(lat_range[0], lat_range[1] + lat_range[2], lat_range[2])
    lons = np.arange(lon_range[0], lon_range[1] + lon_range[2], lon_range[2])

    # Создаем фигуру ТОЛЬКО с одной осью
    fig, ax = plt.subplots(1, 1, figsize=(14, 7))

    # Карта TEC с траекториями спутников
    contour = ax.contourf(lons, lats, tec_map, levels=50, cmap="jet", alpha=0.7)
    cbar = plt.colorbar(contour, ax=ax, label="TECU (10¹⁶ el/m²)")
    cbar.ax.tick_params(labelsize=10)

    # Цвета для разных спутников
    colors = [
        "red",
        "green",
        "blue",
        "purple",
        "orange",
        "cyan",
        "magenta",
        "yellow",
        "black",
        "white",
    ]
    markers = ["o", "s", "^", "v", "<", ">", "p", "*", "X", "D"]

    # Рисуем траектории и текущие позиции выбранных спутников
    for idx, prn in enumerate(selected_prns):
        if prn in satellites_data:
            sat_data = satellites_data[prn]

            # Находим данные для ближайшего времени к эпохе карты TEC
            closest_data = None
            min_time_diff = timedelta(days=365)

            for data in sat_data:
                time_diff = abs(data["epoch"] - epoch)
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    closest_data = data

            if closest_data:
                # Рисуем текущую позицию спутника
                ax.scatter(
                    closest_data["lon"],
                    closest_data["lat"],
                    color=colors[idx % len(colors)],
                    marker=markers[idx % len(markers)],
                    s=120,
                    label=f"R{prn:02d}",
                    edgecolor="black",
                    linewidth=2,
                    zorder=5,
                )

                # Рисуем стрелку направления движения
                speed = sqrt(
                    closest_data["Vx"] ** 2
                    + closest_data["Vy"] ** 2
                    + closest_data["Vz"] ** 2
                )
                if speed > 0:
                    # Упрощенное направление по изменению координат
                    # Уменьшаем масштаб стрелки для лучшей визуализации
                    dx = closest_data["Vx"] * 0.05
                    dy = closest_data["Vy"] * 0.05
                    ax.arrow(
                        closest_data["lon"],
                        closest_data["lat"],
                        dx,
                        dy,
                        head_width=1.5,
                        head_length=2,
                        fc=colors[idx % len(colors)],
                        ec="black",
                        zorder=6,
                        alpha=0.8,
                    )

            # Рассчитываем и рисуем наземную трассу
            ground_track = calculate_satellite_ground_track(sat_data)
            if ground_track and len(ground_track) > 1:
                lons_track, lats_track = zip(*ground_track)
                ax.plot(
                    lons_track,
                    lats_track,
                    color=colors[idx % len(colors)],
                    linewidth=3,
                    alpha=0.8,
                    linestyle="-",
                    zorder=4,
                )

                # Добавляем маркеры вдоль траектории
                if len(ground_track) > 10:
                    # Берем каждую 10-ю точку для маркеров
                    step = len(ground_track) // 10
                    for j in range(0, len(ground_track), step):
                        lon_m, lat_m = ground_track[j]
                        ax.scatter(
                            lon_m,
                            lat_m,
                            color=colors[idx % len(colors)],
                            marker=markers[idx % len(markers)],
                            s=40,
                            alpha=0.6,
                            zorder=4,
                        )

    # Настройки осей
    ax.set_xlabel("Долгота (°)", fontsize=12)
    ax.set_ylabel("Широта (°)", fontsize=12)

    title = f"Карта вертикального электронного содержания (VTEC) с траекториями ГЛОНАСС КА\n"
    title += f"Время: {epoch.strftime('%Y-%m-%d %H:%M UTC')}"
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)

    ax.grid(True, alpha=0.3, linestyle="--")
    ax.legend(loc="upper right", fontsize=10, framealpha=0.9)

    # Устанавливаем границы карты
    ax.set_xlim([lon_range[0], lon_range[1]])
    ax.set_ylim([lat_range[0], lat_range[1]])

    # Добавляем сетку с координатами
    ax.set_xticks(np.arange(lon_range[0], lon_range[1] + 30, 30))
    ax.set_yticks(np.arange(lat_range[0], lat_range[1] + 30, 30))

    # Улучшаем читаемость подписей
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Добавляем информационную панель в углу
    info_text = f"Всего спутников: {len(selected_prns)}\n"
    info_text += f"Время эпохи: {epoch.strftime('%H:%M UTC')}\n"
    info_text += f"Макс TEC: {tec_map.max():.1f} TECU\n"
    info_text += f"Мин TEC: {tec_map.min():.1f} TECU"

    # Добавляем текстовую панель
    props = dict(boxstyle="round", facecolor="wheat", alpha=0.8)
    ax.text(
        0.02,
        0.98,
        info_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=props,
    )

    plt.show()

    # Выводим информацию о спутниках в консоль
    print("\n" + "=" * 70)
    print("ИНФОРМАЦИЯ О СПУТНИКАХ ГЛОНАСС:")
    print("=" * 70)

    total_sats = 0
    for prn in selected_prns:
        if prn in satellites_data and satellites_data[prn]:
            total_sats += 1
            sat_data = satellites_data[prn][0]  # первая эпоха
            print(f"\nСпутник R{prn:02d}:")
            print(f"  Время: {sat_data['epoch'].strftime('%H:%M:%S UTC')}")
            print(f"  Координаты: {sat_data['lat']:.2f}°N, {sat_data['lon']:.2f}°E")
            print(f"  Высота: {sat_data['height']:.0f} км")
            speed = sqrt(
                sat_data["Vx"] ** 2 + sat_data["Vy"] ** 2 + sat_data["Vz"] ** 2
            )
            print(f"  Скорость: {speed:.1f} км/с")
            print(f"  Частотный канал: {sat_data.get('frequency_channel', 'N/A')}")
            print(
                f"  Состояние: {'Рабочий' if sat_data.get('health', 1) == 1 else 'Неисправен'}"
            )

    print(f"\nВсего обработано спутников: {total_sats}")
    print("=" * 70)


# Основная программа
if __name__ == "__main__":
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D

    # Парсим файл IONEX
    ionex_file = "IACG0010.21I"
    print(f"Парсинг файла IONEX: {ionex_file}")
    maps, header = parse_ionex_simple(ionex_file)

    if maps:
        print(f"Успешно прочитано карт TEC: {len(maps)}")
        print(f"Размер карты: {maps[0]['tec'].shape}")
        print(f"Диапазон широт: {header.get('lat_range')}")
        print(f"Диапазон долгот: {header.get('lon_range')}")

        # Парсим файл навигации ГЛОНАСС
        nav_file = "brdc0010.21g"  # предполагаем, что файл находится в той же папке
        print(f"\nПарсинг файла навигации ГЛОНАСС: {nav_file}")

        try:
            satellites_data = parse_glonass_nav(nav_file)
            print(f"Успешно прочитано спутников: {len(satellites_data)}")

            # Выбираем 3 спутника для отображения (например, 1, 2, 3)
            selected_satellites = [1, 2, 3]

            # Проверяем, есть ли данные для выбранных спутников
            available_satellites = [
                prn for prn in selected_satellites if prn in satellites_data
            ]
            if not available_satellites:
                print("Нет данных для выбранных спутников. Доступные спутники:")
                print(sorted(list(satellites_data.keys())))
                available_satellites = sorted(list(satellites_data.keys()))[:3]

            # Выводим первую карту TEC с траекториями спутников
            print(
                f"\nОтображение карты TEC и траекторий спутников: {available_satellites}"
            )
            plot_tec_map_with_satellites(
                maps[0]["tec"],
                header,
                maps[0]["epoch"],
                satellites_data,
                selected_prns=available_satellites[:3],  # максимум 3 для наглядности
            )

        except FileNotFoundError:
            print(f"Файл {nav_file} не найден!")
            print(
                "Скачайте его с CDDIS: https://cddis.nasa.gov/archive/gnss/data/daily/2021/001/21n/brdc0010.21l"
            )

            # Рисуем просто карту TEC без спутников
            print("\nОтображение только карты TEC (без данных спутников)...")
            plot_tec_map(maps[0]["tec"], header, maps[0]["epoch"])
    else:
        print("Не удалось прочитать данные IONEX!")
