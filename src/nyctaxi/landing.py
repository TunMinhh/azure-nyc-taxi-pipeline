import urllib.request
import urllib.error
import os 


def remove_if_exists(temp_path: str) -> None:
    if os.path.exists(temp_path):
        os.remove(temp_path)

def file_download(month, target_dir):
    url = f"https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{month}.parquet"

    filename = url.rsplit("/", 1)[-1]

    os.makedirs(target_dir, exist_ok=True)

    target_path = os.path.join(target_dir, filename)
    temp_path = target_path + ".temp"

    if os.path.exists(target_path):
        return "skipped", target_path
    else:
        try:
            urllib.request.urlretrieve(url, temp_path)
            os.replace(temp_path, target_path)
            return "successful", target_path

        except urllib.error.HTTPError as e:
            remove_if_exists(temp_path)
            if e.code in (403, 404):
                return "not_available", target_path
            raise

        except Exception:
            remove_if_exists(temp_path)
            raise

def month_range(start: str, end: str) -> list[str]:
    start_year, start_month = map(int, start.split("-"))
    end_year, end_month = map(int, end.split("-"))

    months = []
    while (start_year, start_month) <= (end_year, end_month):
        months.append(f"{start_year}-{start_month:02d}")
        if start_month == 12:
            start_year, start_month = start_year + 1, 1
        else:
            start_month += 1

    return months

def land_yellow(start: str, end: str, target_dir: str) -> None:
    months = month_range(start, end)
    for month in months:
        status, path = file_download(month, target_dir)
        print(status, path)

        if status == 'not_available': 
            print(f"Data from {month} is not available, stop here")
            break

if __name__ == "__main__":
    land_yellow("2025-01", "2025-03", "data/yellow")