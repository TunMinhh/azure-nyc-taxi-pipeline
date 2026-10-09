import urllib.request
import urllib.error
import os 


def remove_if_exists(temp_path: str) -> None:
    if os.path.exists(temp_path):
        os.remove(temp_path)

def file_download(url, target_dir):
    filename = url.rsplit("/", 1)[-1]

    os.makedirs(target_dir, exist_ok=True)

    # create a temp path in case theres something intercept the downloading 
    target_path = os.path.join(target_dir, filename)
    temp_path = target_path + ".temp"

    if os.path.exists(target_path):
        return "skipped", target_path
    else:
        try:
            urllib.request.urlretrieve(url, temp_path)
            os.replace(temp_path, target_path) # change from temp file to usable file if the downloading is finished
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

def land_source(cfg: dict, start: str, end: str, target_dir: str) -> None:
    if not cfg["monthly"]: 
        status, path = file_download(cfg["url"], target_dir)
        print(status, path)
        return

    months = month_range(start, end)
    for month in months:
        url = cfg["url"].format(month=month)        # .format() is to replace {month} in the .yml url to the month variable of the loop
        status, path = file_download(url, target_dir)
        print(status, path)

        if status == 'not_available': 
            print(f"Data from {month} is not available, stop here")
            break

# local test
if __name__ == "__main__":
    import yaml

    with open("config/sources.yml") as f:
        config = yaml.safe_load(f)

    green_cfg = config["sources"]["green"]
    land_source(green_cfg, "2025-1", "2025-3", "data/green") 

    yellow_cfg = config["sources"]["yellow"]
    land_source(yellow_cfg, "2025-1", "2025-3", "data/yellow") 

    zones_cfg = config["sources"]["zones"]
    land_source(zones_cfg,0,0,"data/zones")