import pandas as pd


def process_maps(csv_file_path):
    df = pd.read_csv(csv_file_path)
    existing_columns = df.columns.tolist()

    required_columns = ["kacky_id", "author", "event", "prefix"]
    legal_columns = ["at", "difficulty", "tmx_id", "tm_uid"]

    missing_columns = [
        column for column in required_columns if column not in existing_columns
    ]
    extra_columns = [
        column
        for column in existing_columns
        if column not in required_columns + legal_columns
    ]

    if missing_columns:
        return -1

    if extra_columns:
        return -3

    missing_values = df[required_columns].isnull().any(axis=1)
    if missing_values.any():
        return -2

    # add not-set columns so we have a unified format
    for lc in legal_columns:
        if lc not in existing_columns:
            df[lc] = 0
    # Convert DataFrame to a list of lists with specific column order
    column_order = [
        "prefix",
        "kacky_id",
        "author",
        "event",
        "at",
        "difficulty",
        "tmx_id",
        "tm_uid",
    ]
    data = df[column_order].values.tolist()

    return data
