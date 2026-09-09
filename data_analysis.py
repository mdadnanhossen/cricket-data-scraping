"""
data_analysis.py
Data Cleaning + Data Insight on doctors_data.csv
"""

import re
import pandas as pd
import matplotlib.pyplot as plt

INPUT_FILE = "doctors_data.csv"
OUTPUT_FILE = "cleaned_doctors_data.csv"

COLUMNS = [
    "doctor_name", "specialty", "qualification", "designation",
    "hospital", "location", "experience", "profile_url"
]


# ---------------------------------------------------------------
# DATA CLEANING
# ---------------------------------------------------------------

def load_data(path):
    df = pd.read_csv(path)
    print("=" * 60)
    print("STEP 1: RAW DATA OVERVIEW")
    print("=" * 60)
    print(f"Rows: {df.shape[0]}")
    print(f"Columns: {df.shape[1]}")
    print("\nColumn data types:")
    print(df.dtypes)
    print("\nMissing values per column (before cleaning):")
    print(df.isna().sum())
    return df


def remove_duplicates(df):
    before = len(df)
    df = df.drop_duplicates(subset="profile_url", keep="first")
    after = len(df)
    print(f"\nRemoved {before - after} duplicate rows (by profile_url).")
    return df


def clean_whitespace(df):
    text_cols = [c for c in COLUMNS if c != "profile_url"]
    for col in text_cols:
        df[col] = df[col].astype(str).apply(lambda x: re.sub(r"\s+", " ", x).strip())
    return df


def handle_missing_values(df):
    df = df.replace(
        ["", "nan", "NaN", "None", "none", "null", "N/A", "n/a", "NA"], "N/A"
    )
    df = df.fillna("N/A")
    return df


def clean_experience(df):
    def parse_experience(value):
        value = str(value).strip()
        if value in ("N/A", ""):
            return "N/A"
        match = re.search(r"(\d+)\s*\+?\s*year", value, re.IGNORECASE)
        if match:
            return f"{match.group(1)}+ Years"
        return "N/A"

    df["experience"] = df["experience"].apply(parse_experience)
    return df


def clean_data(df):
    print("\n" + "=" * 60)
    print("STEP 2: CLEANING DATA")
    print("=" * 60)

    df = remove_duplicates(df)
    df = clean_whitespace(df)
    df = handle_missing_values(df)
    df = clean_experience(df)

    df = df[COLUMNS]  # keep exact 8 columns, same order

    print(f"\nFinal cleaned row count: {len(df)}")
    print(f"Final column count: {len(df.columns)}")
    return df


# ---------------------------------------------------------------
# DATA INSIGHT
# ---------------------------------------------------------------

def show_basic_insight(df):
    print("\n" + "=" * 60)
    print("STEP 3: DATA INSIGHTS")
    print("=" * 60)
    print(f"\nTotal number of doctors: {len(df)}")


def show_top_values(df, column, title, n=10):
    print(f"\nTop {n} {title}:")
    counts = df[df[column] != "N/A"][column].value_counts().head(n)
    print(counts.to_string())
    return counts


def analyze_experience(df):
    print("\nExperience analysis:")
    exp_df = df[df["experience"] != "N/A"].copy()
    total_with_exp = len(exp_df)
    total = len(df)
    print(f"Doctors with experience info: {total_with_exp} out of {total} "
          f"({total_with_exp / total * 100:.1f}%)")

    if total_with_exp > 0:
        exp_df["years"] = exp_df["experience"].str.extract(r"(\d+)").astype(int)
        print(f"Minimum experience: {exp_df['years'].min()}+ Years")
        print(f"Maximum experience: {exp_df['years'].max()}+ Years")
        print(f"Average experience: {exp_df['years'].mean():.1f}+ Years")
    return exp_df if total_with_exp > 0 else None


def show_missing_stats(df):
    print("\nMissing value statistics (after cleaning, as 'N/A'):")
    for col in COLUMNS:
        na_count = (df[col] == "N/A").sum()
        pct = na_count / len(df) * 100
        print(f"{col}: {na_count} ({pct:.1f}%)")


# ---------------------------------------------------------------
# CHARTS
# ---------------------------------------------------------------

def save_bar_chart(counts, title, xlabel, filename):
    plt.figure(figsize=(10, 6))
    counts.sort_values().plot(kind="barh", color="steelblue")
    plt.title(title)
    plt.xlabel(xlabel)
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()
    print(f"Saved chart: {filename}")


def save_experience_chart(exp_df, filename):
    if exp_df is None or len(exp_df) == 0:
        print("No experience data available for chart.")
        return
    plt.figure(figsize=(8, 6))
    plt.hist(exp_df["years"], bins=10, color="seagreen", edgecolor="black")
    plt.title("Distribution of Doctor Experience (Years)")
    plt.xlabel("Years of Experience")
    plt.ylabel("Number of Doctors")
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()
    print(f"Saved chart: {filename}")


def generate_charts(df, specialty_counts, location_counts, hospital_counts, exp_df):
    print("\n" + "=" * 60)
    print("STEP 4: GENERATING CHARTS")
    print("=" * 60)
    save_bar_chart(specialty_counts, "Top 10 Specialties", "Number of Doctors",
                    "top_specialties.png")
    save_bar_chart(location_counts, "Top 10 Locations", "Number of Doctors",
                    "top_locations.png")
    save_bar_chart(hospital_counts, "Top 10 Hospitals", "Number of Doctors",
                    "top_hospitals.png")
    save_experience_chart(exp_df, "experience_distribution.png")


# ---------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------

def main():
    df = load_data(INPUT_FILE)
    df = clean_data(df)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")
    print(f"\nCleaned data saved to: {OUTPUT_FILE}")

    show_basic_insight(df)
    specialty_counts = show_top_values(df, "specialty", "Specialties")
    location_counts = show_top_values(df, "location", "Locations")
    hospital_counts = show_top_values(df, "hospital", "Hospitals")
    designation_counts = show_top_values(df, "designation", "Designations")
    exp_df = analyze_experience(df)
    show_missing_stats(df)

    generate_charts(df, specialty_counts, location_counts, hospital_counts, exp_df)

    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()