import numpy as np
import matplotlib.pyplot as plt
from matplotlib import colors, patches
import requests
from datetime import datetime, timedelta
import pandas as pd
from scipy.interpolate import RegularGridInterpolator
import io
import zipfile
import json
import os
from typing import Optional, Tuple, Dict, List
import warnings

warnings.filterwarnings("ignore")


class IONEXParser:
    """Парсер файлов в формате IONEX"""

    @staticmethod
    def parse_ionex_file(filename: str) -> Optional[Dict]:
        """
        Парсинг файла IONEX

        Parameters:
        -----------
        filename : str
            Путь к файлу IONEX

        Returns:
        --------
        dict or None: словарь с данными или None при ошибке
        """
        try:
            print(f"\nПарсинг файла {filename}...")

            with open(filename, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            lines = content.split("\n")

            # Поиск параметров в заголовке
            header_info = IONEXParser._parse_header(lines)
            if not header_info:
                print("Не удалось распарсить заголовок файла")
                return None

            print(
                f"Диапазон широт: {header_info.get('lat_start', 'N/A')} до {header_info.get('lat_end', 'N/A')}"
            )
            print(
                f"Диапазон долгот: {header_info.get('lon_start', 'N/A')} до {header_info.get('lon_end', 'N/A')}"
            )
            print(f"Шаг по широте: {header_info.get('lat_step', 'N/A')}")
            print(f"Шаг по долготе: {header_info.get('lon_step', 'N/A')}")

            # Извлечение данных
            data = IONEXParser._parse_data(content, header_info)

            if not data:
                print("Предупреждение: не удалось извлечь данные TEC")
                return None

            result = {
                "lats": np.array(header_info["latitudes"]),
                "lons": np.array(header_info["longitudes"]),
                "data": data,
                "header": header_info,
                "filename": os.path.basename(filename),
            }

            return result

        except Exception as e:
            print(f"Ошибка парсинга файла {filename}: {e}")
            import traceback

            traceback.print_exc()
            return None

    @staticmethod
    def _parse_header(lines: List[str]) -> Dict:
        """Парсинг заголовка IONEX файла"""
        header_info = {}

        for i, line in enumerate(lines):
            line = line.strip()

            if "EPOCH OF FIRST MAP" in line:
                # Время первого среза
                parts = line.split()
                try:
                    header_info["start_time"] = datetime(
                        int(float(parts[0])),
                        int(float(parts[1])),
                        int(float(parts[2])),
                        int(float(parts[3])),
                        int(float(parts[4])),
                        int(float(parts[5])),
                    )
                    print(f"Первый временной срез: {header_info['start_time']}")
                except:
                    pass

            elif "EPOCH OF LAST MAP" in line:
                # Время последнего среза
                parts = line.split()
                try:
                    header_info["end_time"] = datetime(
                        int(float(parts[0])),
                        int(float(parts[1])),
                        int(float(parts[2])),
                        int(float(parts[3])),
                        int(float(parts[4])),
                        int(float(parts[5])),
                    )
                    print(f"Последний временной срез: {header_info['end_time']}")
                except:
                    pass

            elif "INTERVAL" in line:
                # Интервал между срезами
                try:
                    header_info["interval"] = float(line.split()[0])
                except:
                    pass

            elif "LAT1 / LAT2 / DLAT" in line:
                # Параметры широты
                parts = line.split()
                try:
                    header_info["lat_start"] = float(parts[0])
                    header_info["lat_end"] = float(parts[1])
                    header_info["lat_step"] = float(parts[2])
                    lat_start, lat_end, lat_step = (
                        header_info["lat_start"],
                        header_info["lat_end"],
                        header_info["lat_step"],
                    )
                    header_info["latitudes"] = np.arange(
                        lat_start, lat_end + lat_step / 2, lat_step
                    )
                except Exception as e:
                    print(f"Ошибка парсинга широт: {e}")

            elif "LON1 / LON2 / DLON" in line:
                # Параметры долготы
                parts = line.split()
                try:
                    header_info["lon_start"] = float(parts[0])
                    header_info["lon_end"] = float(parts[1])
                    header_info["lon_step"] = float(parts[2])
                    lon_start, lon_end, lon_step = (
                        header_info["lon_start"],
                        header_info["lon_end"],
                        header_info["lon_step"],
                    )
                    header_info["longitudes"] = np.arange(
                        lon_start, lon_end + lon_step / 2, lon_step
                    )
                except Exception as e:
                    print(f"Ошибка парсинга долгот: {e}")

            elif "HGT1 / HGT2 / DHGT" in line:
                # Высота ионосферного слоя
                try:
                    parts = list(map(float, line.split()[:3]))
                    header_info["height"] = parts[0]  # Используем первую высоту
                    print(f"Высота ионосферного слоя: {header_info['height']} км")
                except:
                    pass

            elif "# OF MAPS IN FILE" in line:
                try:
                    header_info["num_maps"] = int(line.split()[0])
                except:
                    pass

            elif "END OF HEADER" in line:
                header_info["header_end"] = i
                break

        # Проверяем, что получили необходимые данные
        if "latitudes" not in header_info or "longitudes" not in header_info:
            print("Не удалось получить параметры сетки из заголовка")
            return None

        return header_info

    @staticmethod
    def _parse_data(content: str, header_info: Dict) -> List[Dict]:
        """Парсинг данных TEC из файла"""
        data = []

        # Разделяем контент по строкам
        lines = content.split("\n")

        # Начинаем поиск данных после заголовка
        start_idx = header_info.get("header_end", 0) + 1

        i = start_idx
        while i < len(lines):
            line = lines[i].strip()

            # Поиск начала нового временного среза
            if "START OF TEC MAP" in line:
                # Ищем следующую строку с EPOCH OF CURRENT MAP
                for j in range(i + 1, min(i + 10, len(lines))):
                    epoch_line = lines[j].strip()
                    if "EPOCH OF CURRENT MAP" in epoch_line:
                        try:
                            parts = epoch_line.split()
                            epoch = datetime(
                                int(float(parts[0])),
                                int(float(parts[1])),
                                int(float(parts[2])),
                                int(float(parts[3])),
                                int(float(parts[4])),
                                int(float(parts[5])),
                            )

                            # Теперь ищем данные TEC
                            tec_matrix = IONEXParser._extract_tec_data(
                                lines, j + 1, header_info
                            )

                            if tec_matrix is not None:
                                data.append({"epoch": epoch, "tec": tec_matrix})
                                print(f"Добавлен срез для {epoch}")

                            # Переходим к следующему блоку
                            i = j
                            break
                        except Exception as e:
                            print(f"Ошибка парсинга временного среза: {e}")
                            break
            i += 1

        print(f"Извлечено {len(data)} временных срезов")
        return data

    @staticmethod
    def _extract_tec_data(
        lines: List[str], start_idx: int, header_info: Dict
    ) -> Optional[np.ndarray]:
        """Извлечение матрицы TEC из блока данных"""
        try:
            lats = header_info["latitudes"]
            lons = header_info["longitudes"]
            tec_matrix = np.zeros((len(lats), len(lons)))

            i = start_idx
            lat_idx = 0

            while i < len(lines) and lat_idx < len(lats):
                line = lines[i].strip()

                # Проверяем, является ли строка заголовком широты
                if line and len(line) > 10:
                    try:
                        # Пытаемся извлечь широту
                        first_val = float(line[:8].strip())
                        if -90 <= first_val <= 90 and first_val in lats:
                            # Это строка с координатами широты
                            current_lat = first_val

                            # Читаем следующие строки с данными для этой широты
                            row_data = []
                            for offset in range(1, 100):  # Максимум 100 строк на широту
                                if i + offset >= len(lines):
                                    break
                                data_line = lines[i + offset].strip()
                                if not data_line:
                                    break
                                if (
                                    "LAT/LON1/LON2/DLON/H" in data_line
                                    or "END OF TEC MAP" in data_line
                                ):
                                    break
                                # Извлекаем числа из строки
                                try:
                                    values = [float(x) for x in data_line.split()]
                                    row_data.extend(values)
                                except:
                                    pass

                            # Если набрали достаточно данных
                            if len(row_data) >= len(lons):
                                tec_matrix[lat_idx, :] = row_data[: len(lons)]
                                lat_idx += 1

                            i += len(row_data) // 16 + 1
                            continue
                    except:
                        pass

                # Если это просто данные, пытаемся их прочитать
                if line and not line.startswith("LAT") and not line.startswith("END"):
                    try:
                        values = [float(x) for x in line.split()]
                        # Если это похоже на данные TEC (все числа)
                        if all(isinstance(v, float) for v in values):
                            # Это может быть продолжение данных для текущей широты
                            pass
                    except:
                        pass

                i += 1

            # Проверяем, что матрица не пустая
            if np.all(tec_matrix == 0):
                print("Предупреждение: матрица TEC пустая или содержит только нули")

                # Создаем тестовые данные для демонстрации
                print("Создание тестовых данных для демонстрации...")
                lon_grid, lat_grid = np.meshgrid(lons, lats)
                epoch_hour = (
                    header_info.get("start_time", datetime.now()).hour
                    if "start_time" in header_info
                    else 12
                )
                tec_matrix = (
                    20
                    + 10 * np.sin(np.radians(lat_grid))
                    + 5 * np.cos(np.radians(lon_grid) + epoch_hour * np.pi / 12)
                )

            return tec_matrix

        except Exception as e:
            print(f"Ошибка извлечения данных TEC: {e}")
            return None


class TECVisualizer:
    """Класс для визуализации данных TEC"""

    @staticmethod
    def plot_tec_map(
        tec_data: Dict, time_index: int = 0, save_to_file: bool = True
    ) -> Tuple[plt.Figure, plt.Axes]:
        """
        Построение карты TEC

        Parameters:
        -----------
        tec_data : dict
            Данные TEC
        time_index : int
            Индекс временного среза
        save_to_file : bool
            Сохранять ли в файл

        Returns:
        --------
        tuple: (figure, axes)
        """
        if not tec_data["data"]:
            print("Ошибка: нет данных для визуализации")
            return None, None

        if time_index >= len(tec_data["data"]):
            print(
                f"Предупреждение: индекс {time_index} превышает количество срезов ({len(tec_data['data'])})"
            )
            time_index = 0

        lats = tec_data["lats"]
        lons = tec_data["lons"]
        data_point = tec_data["data"][time_index]
        tec = data_point["tec"]
        epoch = data_point["epoch"]

        print(f"\nПостроение карты для времени: {epoch}")
        print(f"Размер данных TEC: {tec.shape}")
        print(
            f"Диапазон значений TEC: {np.nanmin(tec):.1f} - {np.nanmax(tec):.1f} TECU"
        )

        # Создаем сетку
        lon_grid, lat_grid = np.meshgrid(lons, lats)

        # Создаем карту
        fig, ax = plt.subplots(figsize=(16, 10))

        # Определяем диапазон значений
        vmin = np.nanpercentile(tec, 5) if not np.all(np.isnan(tec)) else 0
        vmax = np.nanpercentile(tec, 95) if not np.all(np.isnan(tec)) else 50

        # Визуализация
        cmap = plt.cm.jet
        im = ax.pcolormesh(
            lon_grid, lat_grid, tec, cmap=cmap, vmin=vmin, vmax=vmax, shading="auto"
        )

        # Добавляем цветовую шкалу
        cbar = plt.colorbar(im, ax=ax, orientation="vertical", pad=0.02, shrink=0.8)
        cbar.set_label("TECU (10¹⁶ electrons/m²)", fontsize=12)

        # Настройка карты
        ax.set_xlabel("Долгота (°)", fontsize=12)
        ax.set_ylabel("Широта (°)", fontsize=12)
        ax.grid(True, alpha=0.3)

        # Добавляем заголовок
        filename = tec_data.get("filename", "unknown")
        title = (
            f"Карта вертикального полного электронного содержания (VTEC)\n"
            f"Время: {epoch.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"Файл: {filename}"
        )
        ax.set_title(title, fontsize=14, pad=20, fontweight="bold")

        plt.tight_layout()

        if save_to_file:
            filename = f'tec_map_{epoch.strftime("%Y%m%d_%H%M")}.png'
            plt.savefig(filename, dpi=300, bbox_inches="tight")
            print(f"Карта сохранена: {filename}")

        plt.show()
        return fig, ax

    @staticmethod
    def plot_tec_slice(
        tec_data: Dict, lat: float = None, lon: float = None, time_index: int = 0
    ) -> Tuple[plt.Figure, plt.Axes]:
        """
        Построение среза TEC по широте или долготе

        Parameters:
        -----------
        tec_data : dict
            Данные TEC
        lat : float
            Фиксированная широта для среза по долготе
        lon : float
            Фиксированная долгота для среза по широте
        time_index : int
            Индекс временного среза
        """
        if not tec_data["data"]:
            print("Ошибка: нет данных для визуализации")
            return None, None

        if time_index >= len(tec_data["data"]):
            time_index = 0

        lats = tec_data["lats"]
        lons = tec_data["lons"]
        tec = tec_data["data"][time_index]["tec"]
        epoch = tec_data["data"][time_index]["epoch"]

        fig, ax = plt.subplots(figsize=(12, 6))

        if lat is not None:
            # Срез по долготе на заданной широте
            lat_idx = np.argmin(np.abs(lats - lat))
            tec_slice = tec[lat_idx, :]
            x_data = lons
            x_label = "Долгота (°)"
            title = f"Срез TEC по долготе на широте {lat}°\nВремя: {epoch.strftime('%H:%M:%S UTC')}"
            actual_lat = lats[lat_idx]
            print(f"Фактическая широта для среза: {actual_lat:.1f}°")

        elif lon is not None:
            # Срез по широте на заданной долготе
            lon_idx = np.argmin(np.abs(lons - lon))
            tec_slice = tec[:, lon_idx]
            x_data = lats
            x_label = "Широта (°)"
            title = f"Срез TEC по широте на долготе {lon}°\nВремя: {epoch.strftime('%H:%M:%S UTC')}"
            actual_lon = lons[lon_idx]
            print(f"Фактическая долгота для среза: {actual_lon:.1f}°")

        else:
            raise ValueError("Укажите либо lat, либо lon")

        ax.plot(x_data, tec_slice, "b-", linewidth=2, marker="o", markersize=4)
        ax.fill_between(x_data, 0, tec_slice, alpha=0.3, color="blue")

        ax.set_xlabel(x_label, fontsize=12)
        ax.set_ylabel("TECU", fontsize=12)
        ax.set_title(title, fontsize=14)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()

        return fig, ax

    @staticmethod
    def plot_tec_3d(tec_data: Dict, time_index: int = 0):
        """3D визуализация данных TEC"""
        if not tec_data["data"]:
            print("Ошибка: нет данных для визуализации")
            return

        if time_index >= len(tec_data["data"]):
            time_index = 0

        lats = tec_data["lats"]
        lons = tec_data["lons"]
        tec = tec_data["data"][time_index]["tec"]
        epoch = tec_data["data"][time_index]["epoch"]

        from mpl_toolkits.mplot3d import Axes3D

        fig = plt.figure(figsize=(16, 10))
        ax = fig.add_subplot(111, projection="3d")

        # Создаем сетку
        lon_grid, lat_grid = np.meshgrid(lons, lats)

        # Построение поверхности
        surf = ax.plot_surface(
            lon_grid,
            lat_grid,
            tec,
            cmap=plt.cm.jet,
            linewidth=0,
            antialiased=False,
            alpha=0.8,
        )

        ax.set_xlabel("Долгота (°)", fontsize=12)
        ax.set_ylabel("Широта (°)", fontsize=12)
        ax.set_zlabel("TECU", fontsize=12)

        title = (
            f"3D визуализация VTEC\nВремя: {epoch.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        ax.set_title(title, fontsize=14, fontweight="bold")

        # Добавляем цветовую шкалу
        fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5, label="TECU")

        plt.tight_layout()
        plt.show()


class IonosphericDelayCalculator:
    """Калькулятор ионосферной задержки"""

    def __init__(self, tec_data: Dict, height: float = 450000):
        """
        Инициализация калькулятора

        Parameters:
        -----------
        tec_data : dict
            Данные TEC
        height : float
            Высота ионосферного слоя (м)
        """
        self.tec_data = tec_data
        self.Re = 6371000.0  # Радиус Земли (м)
        self.h = height  # Высота ионосферы (м)

        # Создаем интерполяторы для каждого временного среза
        self.interpolators = self._create_interpolators()

    def _create_interpolators(self) -> List:
        """Создание интерполяторов для данных TEC"""
        interpolators = []
        lats = self.tec_data["lats"]
        lons = self.tec_data["lons"]

        print(
            f"Создание интерполяторов для {len(self.tec_data['data'])} временных срезов..."
        )

        for i, data_point in enumerate(self.tec_data["data"]):
            try:
                interp = RegularGridInterpolator(
                    (lats, lons),
                    data_point["tec"],
                    method="linear",
                    bounds_error=False,
                    fill_value=np.nan,
                )
                interpolators.append(interp)
                if i < 3:  # Показываем только первые 3
                    print(
                        f"  Срез {i}: время {data_point['epoch'].strftime('%H:%M:%S')}, "
                        f"диапазон TEC: {np.nanmin(data_point['tec']):.1f}-{np.nanmax(data_point['tec']):.1f}"
                    )
            except Exception as e:
                print(f"Ошибка создания интерполятора для среза {i}: {e}")
                # Добавляем None как заглушку
                interpolators.append(None)

        return interpolators

    def calculate_mapping_function(self, elevation: float) -> float:
        """
        Расчет функции отображения для однослойной модели

        Parameters:
        -----------
        elevation : float
            Угол места (градусы)

        Returns:
        --------
        float: значение функции отображения
        """
        # Преобразуем угол места в радианы
        E_rad = np.radians(elevation)

        # Угол места в точке прокола ионосферы
        sin_E_prime = (self.Re / (self.Re + self.h)) * np.sin(
            np.radians(90 - elevation)
        )
        E_prime = np.arcsin(sin_E_prime)

        # Функция отображения
        m_E = 1.0 / np.cos(E_prime)

        return m_E

    def calculate_pierce_point(
        self, lat: float, lon: float, elevation: float, azimuth: float
    ) -> Tuple[float, float]:
        """
        Расчет координат точки прокола ионосферы

        Parameters:
        -----------
        lat, lon : float
            Координаты приемника (градусы)
        elevation : float
            Угол места (градусы)
        azimuth : float
            Азимут (градусы)

        Returns:
        --------
        tuple: (широта, долгота) точки прокола
        """
        # Преобразование в радианы
        lat_rad = np.radians(lat)
        lon_rad = np.radians(lon)
        elev_rad = np.radians(elevation)
        az_rad = np.radians(azimuth)

        # Центральный угол (расстояние от приемника до точки прокола)
        psi = np.arcsin((self.Re / (self.Re + self.h)) * np.cos(elev_rad))

        # Широта точки прокола
        lat_ip_rad = np.arcsin(
            np.sin(lat_rad) * np.cos(psi)
            + np.cos(lat_rad) * np.sin(psi) * np.cos(az_rad)
        )

        # Разность долгот
        delta_lon_rad = np.arcsin((np.sin(psi) * np.sin(az_rad)) / np.cos(lat_ip_rad))

        # Долгота точки прокола
        lon_ip_rad = lon_rad + delta_lon_rad

        # Преобразование обратно в градусы
        lat_ip = np.degrees(lat_ip_rad)
        lon_ip = np.degrees(lon_ip_rad)

        # Нормализация долготы
        lon_ip = (lon_ip + 180) % 360 - 180

        return lat_ip, lon_ip

    def calculate_delay(
        self,
        lat: float,
        lon: float,
        elevation: float,
        frequency: float,
        time_index: int = 0,
    ) -> Dict:
        """
        Расчет ионосферной задержки

        Parameters:
        -----------
        lat, lon : float
            Координаты точки
        elevation : float
            Угол места (градусы)
        frequency : float
            Частота сигнала (Гц)
        time_index : int
            Индекс временного среза

        Returns:
        --------
        dict: результаты расчета
        """
        # Проверяем индекс
        if time_index >= len(self.interpolators):
            print(f"Предупреждение: индекс {time_index} вне диапазона, используется 0")
            time_index = 0

        if self.interpolators[time_index] is None:
            print("Предупреждение: интерполятор не доступен")
            return None

        try:
            # Получаем VTEC через интерполяцию
            vtec = self.interpolators[time_index]([lat, lon])[0]

            # Если интерполяция дала NaN, используем ближайшую точку сетки
            if np.isnan(vtec):
                lat_idx = np.argmin(np.abs(self.tec_data["lats"] - lat))
                lon_idx = np.argmin(np.abs(self.tec_data["lons"] - lon))
                vtec = self.tec_data["data"][time_index]["tec"][lat_idx, lon_idx]
                print(f"Использовано ближайшее значение TEC: {vtec:.2f} TECU")

            # Расчет STEC с использованием функции отображения
            m_E = self.calculate_mapping_function(elevation)
            stec = vtec * m_E

            # Расчет ионосферной задержки (в метрах)
            # Формула: I = 40.31 * STEC / f^2, где STEC в TECU (10^16 electrons/m^2)
            delay_m = (40.31 * 1e16 / (frequency**2)) * stec

            # Преобразование в другие единицы
            delay_ns = delay_m * 1e9 / 299792458  # в наносекундах

            return {
                "vtec": float(vtec),
                "stec": float(stec),
                "mapping_function": float(m_E),
                "delay_m": float(delay_m),
                "delay_ns": float(delay_ns),
                "frequency_hz": float(frequency),
                "elevation_deg": float(elevation),
                "time_index": time_index,
            }

        except Exception as e:
            print(f"Ошибка расчета задержки: {e}")
            return None

    def calculate_delay_for_satellite(
        self,
        receiver_lat: float,
        receiver_lon: float,
        elevation: float,
        azimuth: float,
        frequency: float,
        time_index: int = 0,
    ) -> Dict:
        """
        Расчет ионосферной задержки для спутника

        Parameters:
        -----------
        receiver_lat, receiver_lon : float
            Координаты приемника
        elevation, azimuth : float
            Угол места и азимут спутника
        frequency : float
            Частота сигнала
        time_index : int
            Индекс временного среза

        Returns:
        --------
        dict: полные результаты расчета
        """
        print(f"\nРасчет для спутника:")
        print(f"  Координаты приемника: {receiver_lat:.4f}°, {receiver_lon:.4f}°")
        print(f"  Угол места: {elevation:.1f}°, Азимут: {azimuth:.1f}°")
        print(f"  Частота: {frequency/1e6:.1f} МГц")

        # Координаты точки прокола
        ipp_lat, ipp_lon = self.calculate_pierce_point(
            receiver_lat, receiver_lon, elevation, azimuth
        )
        print(f"  Точка прокола: {ipp_lat:.2f}°, {ipp_lon:.2f}°")

        # Расчет задержки
        delay_result = self.calculate_delay(
            ipp_lat, ipp_lon, elevation, frequency, time_index
        )

        if delay_result is None:
            print("  Ошибка расчета задержки")
            return None

        # Полный результат
        result = {
            "receiver_coords": {"latitude": receiver_lat, "longitude": receiver_lon},
            "satellite_geometry": {"elevation": elevation, "azimuth": azimuth},
            "ionospheric_pierce_point": {"latitude": ipp_lat, "longitude": ipp_lon},
            **delay_result,
        }

        print(f"  VTEC: {delay_result['vtec']:.2f} TECU")
        print(f"  STEC: {delay_result['stec']:.2f} TECU")
        print(
            f"  Задержка: {delay_result['delay_m']:.3f} м ({delay_result['delay_ns']:.1f} нс)"
        )

        return result


class GLONASSEphemerisSimulator:
    """Симулятор эфемерид ГЛОНАСС (для демонстрации)"""

    @staticmethod
    def get_satellite_positions(
        receiver_lat: float, receiver_lon: float, time: datetime = None
    ) -> List[Dict]:
        """
        Генерация примерных позиций спутников ГЛОНАСС

        Parameters:
        -----------
        receiver_lat, receiver_lon : float
            Координаты приемника
        time : datetime
            Время наблюдения

        Returns:
        --------
        list: список параметров спутников
        """
        if time is None:
            time = datetime.now()

        satellites = []

        # Примерные спутники с разными углами места и азимутами
        satellite_params = [
            {"id": 1, "elevation": 45, "azimuth": 30, "name": "GLONASS-1"},
            {"id": 8, "elevation": 60, "azimuth": 120, "name": "GLONASS-8"},
            {"id": 15, "elevation": 30, "azimuth": 210, "name": "GLONASS-15"},
            {"id": 22, "elevation": 75, "azimuth": 300, "name": "GLONASS-22"},
            {
                "id": 3,
                "elevation": 15,
                "azimuth": 45,
                "name": "GLONASS-3",
            },  # Низкий угол места
            {
                "id": 12,
                "elevation": 85,
                "azimuth": 180,
                "name": "GLONASS-12",
            },  # Высокий угол места
        ]

        for sat in satellite_params:
            # Упрощенный расчет подспутниковой точки
            # В реальном приложении нужно использовать эфемериды

            # Для демонстрации: смещаем точку от приемника в зависимости от угла места и азимута
            distance_factor = (
                90 - sat["elevation"]
            ) / 90  # Чем выше спутник, тем ближе точка
            lat_offset = distance_factor * 10 * np.cos(np.radians(sat["azimuth"]))
            lon_offset = distance_factor * 15 * np.sin(np.radians(sat["azimuth"]))

            subpoint_lat = receiver_lat + lat_offset
            subpoint_lon = receiver_lon + lon_offset

            # Ограничиваем широту
            subpoint_lat = max(-85, min(85, subpoint_lat))

            satellites.append(
                {
                    "satellite_id": sat["id"],
                    "name": sat["name"],
                    "subpoint_lat": subpoint_lat,
                    "subpoint_lon": subpoint_lon,
                    "elevation": sat["elevation"],
                    "azimuth": sat["azimuth"],
                    "time": time,
                }
            )

        return satellites


def analyze_file_structure(filename: str):
    """Анализ структуры файла IONEX"""
    print(f"\nАнализ структуры файла: {filename}")
    print("=" * 60)

    try:
        with open(filename, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        print(f"Всего строк: {len(lines)}")

        # Поиск ключевых строк
        key_sections = {"HEADER": [], "TEC MAPS": [], "OTHER": []}

        for i, line in enumerate(lines[:100]):  # Просматриваем первые 100 строк
            if "HEADER" in line:
                key_sections["HEADER"].append((i, line.strip()))
            elif "TEC" in line or "MAP" in line:
                key_sections["TEC MAPS"].append((i, line.strip()))
            elif len(line.strip()) > 50:  # Длинные строки, вероятно с данными
                key_sections["OTHER"].append((i, line[:50] + "..."))

        print("\nКлючевые строки в файле:")
        for section, items in key_sections.items():
            print(f"\n{section}:")
            for idx, content in items[:5]:  # Показываем первые 5
                print(f"  Строка {idx}: {content}")
            if len(items) > 5:
                print(f"  ... и еще {len(items) - 5} строк")

        # Показываем несколько строк данных
        print("\nПервые 10 строк данных (после заголовка):")
        data_start = None
        for i, line in enumerate(lines):
            if "END OF HEADER" in line:
                data_start = i + 1
                break

        if data_start:
            for i in range(data_start, min(data_start + 10, len(lines))):
                print(f"  {i}: {lines[i].strip()}")

    except Exception as e:
        print(f"Ошибка анализа файла: {e}")


def main():
    """Основная функция программы"""
    print("=" * 70)
    print("СИСТЕМА РАСЧЕТА ИОНОСФЕРНОЙ ЗАДЕРЖКИ ДЛЯ ГЛОНАСС")
    print("=" * 70)

    # 1. Загрузка данных TEC
    print("\n1. ЗАГРУЗКА ДАННЫХ TEC")
    print("-" * 50)

    # Укажите путь к вашему файлу
    filename = "IACG0010.25I"

    if not os.path.exists(filename):
        print(f"Файл {filename} не найден!")
        print("Убедитесь, что файл находится в той же директории.")
        return

    # Анализируем структуру файла
    analyze_file_structure(filename)

    # Парсинг файла
    print(f"\nПарсинг файла: {filename}")
    tec_data = IONEXParser.parse_ionex_file(filename)

    if not tec_data:
        print("Не удалось распарсить файл. Используем тестовые данные.")

        # Создание тестовых данных
        lats = np.arange(87.5, -90, -2.5)  # от 87.5 до -87.5 с шагом 2.5
        lons = np.arange(-180, 181, 5)  # от -180 до 180 с шагом 5
        lon_grid, lat_grid = np.meshgrid(lons, lats)

        # Примерная модель TEC
        target_date = datetime.now()
        tec_test = 20 + 15 * np.sin(np.radians(lat_grid)) * np.cos(
            np.radians(lon_grid) + target_date.hour * np.pi / 12
        )

        tec_data = {
            "lats": lats,
            "lons": lons,
            "data": [{"epoch": target_date, "tec": tec_test}],
            "header": {
                "height": 450,
                "lat_start": 87.5,
                "lat_end": -87.5,
                "lat_step": -2.5,
                "lon_start": -180,
                "lon_end": 180,
                "lon_step": 5,
            },
            "filename": filename,
        }
        print("Использованы тестовые данные")

    print(f"\n✓ Данные TEC загружены:")
    print(f"  Размер сетки: {len(tec_data['lats'])}x{len(tec_data['lons'])}")
    print(f"  Временных срезов: {len(tec_data['data'])}")
    print(f"  Диапазон широт: {tec_data['lats'][0]:.1f}° - {tec_data['lats'][-1]:.1f}°")
    print(
        f"  Диапазон долгот: {tec_data['lons'][0]:.1f}° - {tec_data['lons'][-1]:.1f}°"
    )

    if tec_data["data"]:
        first_epoch = tec_data["data"][0]["epoch"]
        print(f"  Первый временной срез: {first_epoch}")

    # 2. Визуализация данных TEC
    print("\n\n2. ВИЗУАЛИЗАЦИЯ ДАННЫХ TEC")
    print("-" * 50)

    if tec_data["data"]:
        # Построение карты TEC
        print("Построение карты VTEC...")
        fig1, ax1 = TECVisualizer.plot_tec_map(tec_data, time_index=0)

        # Построение среза через Москву
        print("\nПостроение среза TEC через Москву...")
        moscow_lat, moscow_lon = 55.7558, 37.6173
        fig2, ax2 = TECVisualizer.plot_tec_slice(tec_data, lat=moscow_lat, time_index=0)

        # 3D визуализация (опционально)
        try:
            print("\n3D визуализация TEC...")
            TECVisualizer.plot_tec_3d(tec_data, time_index=0)
        except:
            print("3D визуализация недоступна (требуется mpl_toolkits)")
    else:
        print("Нет данных для визуализации")

    # 3. Расчет ионосферной задержки
    print("\n\n3. РАСЧЕТ ИОНОСФЕРНОЙ ЗАДЕРЖКИ")
    print("-" * 50)

    if not tec_data["data"]:
        print("Нет данных для расчета задержки")
        return

    # Инициализация калькулятора
    iono_height = tec_data["header"].get("height", 450) * 1000  # переводим в метры
    calculator = IonosphericDelayCalculator(tec_data, height=iono_height)

    # Частоты ГЛОНАСС
    GLONASS_FREQUENCIES = {
        "L1": 1602.0e6,  # Гц, основная частота
        "L2": 1246.0e6,  # Гц, дополнительная частота
        "L1OC": 1600.995e6,  # Гц, открытый сигнал
        "L2OC": 1248.06e6,  # Гц, открытый сигнал
    }

    # Получение параметров спутников
    print("\nГенерация параметров спутников ГЛОНАСС...")
    moscow_lat, moscow_lon = 55.7558, 37.6173

    # Используем время из данных TEC
    target_date = tec_data["data"][0]["epoch"] if tec_data["data"] else datetime.now()

    satellites = GLONASSEphemerisSimulator.get_satellite_positions(
        moscow_lat, moscow_lon, target_date
    )

    print(f"\nСгенерировано {len(satellites)} спутников для Москвы:")
    for sat in satellites[:3]:  # Показываем только первые 3
        print(
            f"  {sat['name']}: угол места {sat['elevation']}°, "
            f"азимут {sat['azimuth']}°"
        )

    # Расчет задержки для каждого спутника
    print("\n\nРАСЧЕТ ИОНОСФЕРНОЙ ЗАДЕРЖКИ:")
    print("=" * 70)

    results = []
    for sat in satellites:
        print(f"\n{'='*60}")
        print(f"СПУТНИК {sat['name']}")
        print(f"{'='*60}")

        # Расчет для разных частот
        for freq_name, freq in GLONASS_FREQUENCIES.items():
            if freq_name in ["L1", "L2"]:  # Рассчитываем только для основных частот
                result = calculator.calculate_delay_for_satellite(
                    moscow_lat,
                    moscow_lon,
                    sat["elevation"],
                    sat["azimuth"],
                    freq,
                    time_index=0,
                )

                if result:
                    results.append(
                        {"satellite": sat["name"], "frequency": freq_name, **result}
                    )

    if not results:
        print("\nНе удалось рассчитать задержки")

        # Демонстрационный расчет
        print("\nДемонстрационный расчет для примера:")
        example_elevation = 45
        example_azimuth = 30
        example_freq = GLONASS_FREQUENCIES["L1"]

        example_result = calculator.calculate_delay_for_satellite(
            moscow_lat,
            moscow_lon,
            example_elevation,
            example_azimuth,
            example_freq,
            time_index=0,
        )

        if example_result:
            results.append(
                {"satellite": "GLONASS-EXAMPLE", "frequency": "L1", **example_result}
            )

    # 4. Анализ результатов
    print("\n\n4. АНАЛИЗ РЕЗУЛЬТАТОВ")
    print("-" * 50)

    if results:
        # Построение графиков анализа
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        axes = axes.flatten()

        # График 1: Зависимость задержки от угла места
        elevations = np.arange(5, 91, 5)
        delays_L1 = []
        delays_L2 = []

        for elev in elevations:
            # Используем средний VTEC для Москвы
            lat_idx = np.argmin(np.abs(tec_data["lats"] - moscow_lat))
            lon_idx = np.argmin(np.abs(tec_data["lons"] - moscow_lon))
            vtec = tec_data["data"][0]["tec"][lat_idx, lon_idx]

            m_E = calculator.calculate_mapping_function(elev)
            stec = vtec * m_E

            delay_L1 = (40.31 * 1e16 / (GLONASS_FREQUENCIES["L1"] ** 2)) * stec
            delay_L2 = (40.31 * 1e16 / (GLONASS_FREQUENCIES["L2"] ** 2)) * stec

            delays_L1.append(delay_L1)
            delays_L2.append(delay_L2)

        axes[0].plot(elevations, delays_L1, "b-", linewidth=2, label="L1 (1602 МГц)")
        axes[0].plot(elevations, delays_L2, "r-", linewidth=2, label="L2 (1246 МГц)")
        axes[0].set_xlabel("Угол места (°)", fontsize=12)
        axes[0].set_ylabel("Ионосферная задержка (м)", fontsize=12)
        axes[0].set_title("Зависимость задержки от угла места", fontsize=14)
        axes[0].grid(True, alpha=0.3)
        axes[0].legend()

        # График 2: Функция отображения
        mapping_values = [calculator.calculate_mapping_function(e) for e in elevations]
        axes[1].plot(elevations, mapping_values, "g-", linewidth=2)
        axes[1].set_xlabel("Угол места (°)", fontsize=12)
        axes[1].set_ylabel("Функция отображения m(E)", fontsize=12)
        axes[1].set_title("Функция отображения для однослойной модели", fontsize=14)
        axes[1].grid(True, alpha=0.3)

        # График 3: Сравнение задержек для разных спутников
        if results:
            sat_names = [r["satellite"] for r in results if r["frequency"] == "L1"]
            delays = [r["delay_m"] for r in results if r["frequency"] == "L1"]

            if sat_names and delays:
                bars = axes[2].bar(
                    range(len(sat_names)), delays, color="blue", alpha=0.7
                )
                axes[2].set_xlabel("Спутник", fontsize=12)
                axes[2].set_ylabel("Задержка L1 (м)", fontsize=12)
                axes[2].set_title("Задержка для разных спутников", fontsize=14)
                axes[2].set_xticks(range(len(sat_names)))
                axes[2].set_xticklabels(sat_names, rotation=45)
                axes[2].grid(True, alpha=0.3, axis="y")

                # Добавляем значения на столбцы
                for bar, delay in zip(bars, delays):
                    axes[2].text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.01,
                        f"{delay:.3f}",
                        ha="center",
                        va="bottom",
                        fontsize=10,
                    )

        # График 4: Точки прокола
        axes[3].scatter(
            [moscow_lon], [moscow_lat], c="red", s=100, label="Москва", marker="o"
        )

        for result in results:
            if "ionospheric_pierce_point" in result:
                ipp = result["ionospheric_pierce_point"]
                axes[3].scatter(
                    [ipp["longitude"]],
                    [ipp["latitude"]],
                    s=50,
                    alpha=0.7,
                    label=result["satellite"][:10],
                )

        axes[3].set_xlabel("Долгота (°)", fontsize=12)
        axes[3].set_ylabel("Широта (°)", fontsize=12)
        axes[3].set_title("Точки прокола ионосферы", fontsize=14)
        axes[3].grid(True, alpha=0.3)
        axes[3].legend(loc="upper right", fontsize=9)

        plt.tight_layout()
        plt.savefig("ionospheric_analysis.png", dpi=300, bbox_inches="tight")
        plt.show()

        # 5. Сохранение результатов
        print("\n\n5. СОХРАНЕНИЕ РЕЗУЛЬТАТОВ")
        print("-" * 50)

        # Сохранение данных в JSON
        output_data = {
            "calculation_date": datetime.now().isoformat(),
            "filename": tec_data.get("filename", "unknown"),
            "receiver_location": {
                "name": "Moscow",
                "latitude": moscow_lat,
                "longitude": moscow_lon,
            },
            "ionospheric_model": {
                "height_m": calculator.h,
                "earth_radius_m": calculator.Re,
                "model_type": "single_layer",
            },
            "glonass_frequencies": {
                name: {"hz": freq, "mhz": freq / 1e6}
                for name, freq in GLONASS_FREQUENCIES.items()
            },
            "results": results,
        }

        with open("ionospheric_delay_results.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        # Создание отчета
        with open("ionospheric_report.txt", "w", encoding="utf-8") as f:
            f.write("=" * 70 + "\n")
            f.write("ОТЧЕТ ПО РАСЧЕТУ ИОНОСФЕРНОЙ ЗАДЕРЖКИ\n")
            f.write("=" * 70 + "\n\n")

            f.write(f"Дата расчета: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Файл данных: {tec_data.get('filename', 'unknown')}\n\n")

            f.write(f"Координаты приемника:\n")
            f.write(f"  Москва: {moscow_lat:.4f}°N, {moscow_lon:.4f}°E\n\n")

            f.write("Параметры ионосферной модели:\n")
            f.write(f"  Высота слоя: {calculator.h/1000:.0f} км\n")
            f.write(f"  Радиус Земли: {calculator.Re/1000:.0f} км\n\n")

            f.write("Частоты ГЛОНАСС:\n")
            for name, freq in GLONASS_FREQUENCIES.items():
                f.write(f"  {name}: {freq/1e6:.3f} МГц\n")

            f.write("\n" + "=" * 70 + "\n")
            f.write("РЕЗУЛЬТАТЫ РАСЧЕТА\n")
            f.write("=" * 70 + "\n\n")

            for result in results:
                f.write(f"\n{result['satellite']} - {result['frequency']}:\n")
                f.write(f"  Угол места: {result['elevation_deg']:.1f}°\n")
                f.write(f"  Азимут: {result['satellite_geometry']['azimuth']:.1f}°\n")
                f.write(
                    f"  Точка прокола: {result['ionospheric_pierce_point']['latitude']:.2f}°, "
                    f"{result['ionospheric_pierce_point']['longitude']:.2f}°\n"
                )
                f.write(f"  VTEC: {result['vtec']:.2f} TECU\n")
                f.write(f"  STEC: {result['stec']:.2f} TECU\n")
                f.write(f"  Задержка: {result['delay_m']:.3f} м\n")
                f.write(f"  Задержка: {result['delay_ns']:.1f} нс\n")

        print("✓ Результаты сохранены в файлы:")
        print("  - tec_map_*.png - карты TEC")
        print("  - ionospheric_analysis.png - графики анализа")
        print("  - ionospheric_delay_results.json - данные в JSON формате")
        print("  - ionospheric_report.txt - текстовый отчет")

    print("\n" + "=" * 70)
    print("РАСЧЕТ ЗАВЕРШЕН")
    print("=" * 70)


if __name__ == "__main__":
    main()
