import ftplib
import os
from datetime import datetime


def download_via_ftp():
    # Параметры FTP сервера
    ftp_host = "ftp.glonass-iac.ru"
    ftp_path = "/MCC/PRODUCTS/ionex/"

    # Имя файла для загрузки (пример)
    filename = "TEC20240115.ION"  # Замените на нужную дату

    # Имя файла для сохранения локально
    local_filename = "tec_data.ion"

    try:
        print(f"Подключение к FTP серверу: {ftp_host}")

        # Подключение к FTP серверу
        ftp = ftplib.FTP(ftp_host)

        # Логин (часто FTP серверы позволяют анонимный доступ)
        ftp.login()  # Анонимный доступ

        # Переход в нужную директорию
        ftp.cwd(ftp_path)

        # Получение списка файлов
        print("Список файлов в директории:")
        files = ftp.nlst()
        for file in files[:10]:  # Покажем первые 10 файлов
            print(f"  - {file}")

        # Загрузка файла
        print(f"\nЗагрузка файла: {filename}")
        with open(local_filename, "wb") as f:
            ftp.retrbinary(f"RETR {filename}", f.write)

        # Закрытие соединения
        ftp.quit()

        print(f"✓ Файл успешно загружен: {local_filename}")
        print(f"Размер файла: {os.path.getsize(local_filename)} байт")

        return local_filename

    except ftplib.error_perm as e:
        print(f"Ошибка доступа к FTP: {e}")
        return None
    except Exception as e:
        print(f"Ошибка при загрузке: {e}")
        return None


def download_with_passive_mode():
    """Загрузка с использованием пассивного режима (часто требуется за фаерволом)"""
    ftp_host = "ftp.glonass-iac.ru"
    ftp_path = "/MCC/PRODUCTS/ionex/"
    filename = "TEC20240115.ION"
    local_filename = "tec_data.ion"

    try:
        print("Подключение с использованием пассивного режима...")

        ftp = ftplib.FTP(ftp_host)
        ftp.login()  # Анонимный доступ
        ftp.set_pasv(True)  # Включаем пассивный режим
        ftp.cwd(ftp_path)

        with open(local_filename, "wb") as f:
            ftp.retrbinary(f"RETR {filename}", f.write)

        ftp.quit()
        print(f"✓ Файл загружен: {local_filename}")

        return local_filename

    except Exception as e:
        print(f"Ошибка: {e}")
        return None


def list_directory_contents():
    """Просмотр содержимого FTP директории"""
    ftp_host = "ftp.glonass-iac.ru"
    ftp_path = "/MCC/PRODUCTS/ionex/"

    try:
        ftp = ftplib.FTP(ftp_host)
        ftp.login()
        ftp.cwd(ftp_path)

        print(f"Содержимое {ftp_path}:")
        print("-" * 50)

        # Детальный список файлов
        ftp.dir()

        # Или более читаемый вывод
        print("\n\nТолько имена файлов:")
        files = ftp.nlst()
        for i, file in enumerate(files, 1):
            print(f"{i:3d}. {file}")

        ftp.quit()

    except Exception as e:
        print(f"Ошибка: {e}")


def download_latest_file():
    """Загрузка последнего файла по дате в имени"""
    ftp_host = "ftp.glonass-iac.ru"
    ftp_path = "/MCC/PRODUCTS/ionex/"

    try:
        ftp = ftplib.FTP(ftp_host)
        ftp.login()
        ftp.cwd(ftp_path)

        # Получаем список файлов
        files = ftp.nlst()

        # Фильтруем файлы TEC (пример паттерна)
        tec_files = [f for f in files if f.startswith("TEC") and f.endswith(".ION")]

        if not tec_files:
            print("Не найдено TEC файлов")
            return None

        # Сортируем по дате (предполагаем формат TECYYYYMMDD.ION)
        tec_files.sort(reverse=True)
        latest_file = tec_files[0]

        print(f"Последний файл: {latest_file}")

        # Загружаем
        local_filename = latest_file
        with open(local_filename, "wb") as f:
            ftp.retrbinary(f"RETR {latest_file}", f.write)

        ftp.quit()
        print(f"✓ Загружен: {local_filename}")

        return local_filename

    except Exception as e:
        print(f"Ошибка: {e}")
        return None


def download_with_progress():
    """Загрузка с отображением прогресса"""
    ftp_host = "ftp.glonass-iac.ru"
    ftp_path = "/MCC/PRODUCTS/ionex/"
    filename = "TEC20240115.ION"
    local_filename = "tec_data.ion"

    class ProgressCallback:
        def __init__(self, total_size=None):
            self.total_size = total_size
            self.downloaded = 0

        def __call__(self, data):
            self.downloaded += len(data)
            if self.total_size:
                percent = (self.downloaded / self.total_size) * 100
                print(
                    f"\rПрогресс: {percent:.1f}% ({self.downloaded}/{self.total_size} байт)",
                    end="",
                )

    try:
        ftp = ftplib.FTP(ftp_host)
        ftp.login()
        ftp.cwd(ftp_path)

        # Получаем размер файла
        ftp.sendcmd("TYPE I")  # Переходим в бинарный режим
        size = ftp.size(filename)
        print(f"Размер файла: {size} байт")

        # Создаем callback для отслеживания прогресса
        callback = ProgressCallback(size)

        # Загружаем файл
        with open(local_filename, "wb") as f:
            ftp.retrbinary(f"RETR {filename}", f.write, callback=callback)

        print()  # Новая строка после прогресса
        ftp.quit()
        print(f"✓ Файл загружен: {local_filename}")

        return local_filename

    except Exception as e:
        print(f"Ошибка: {e}")
        return None


# Пример использования
if __name__ == "__main__":
    print("Примеры загрузки файлов по FTP")
    print("=" * 50)

    # 1. Простая загрузка
    print("\n1. Простая загрузка файла:")
    download_via_ftp()

    # 2. Просмотр содержимого директории
    print("\n2. Просмотр содержимого директории:")
    # list_directory_contents()  # Раскомментируйте для просмотра

    # 3. Загрузка с прогрессом
    print("\n3. Загрузка с отображением прогресса:")
    # download_with_progress()  # Раскомментируйте для использования

    # 4. Загрузка последнего файла
    print("\n4. Загрузка последнего файла:")
    # download_latest_file()  # Раскомментируйте для использования

    # 5. Загрузка конкретного файла с текущей датой
    print("\n5. Загрузка файла для текущей даты:")
    today = datetime.now()
    date_str = today.strftime("%Y%m%d")
    filename = f"TEC{date_str}.ION"
    print(f"Попытка загрузить: {filename}")

    # Для реальной загрузки используйте:
    # ftp = ftplib.FTP("ftp.glonass-iac.ru")
    # ftp.login()
    # ftp.cwd("/MCC/PRODUCTS/ionex/")
    # with open(filename, 'wb') as f:
    #     ftp.retrbinary(f'RETR {filename}', f.write)
    # ftp.quit()
