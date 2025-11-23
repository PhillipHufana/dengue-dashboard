# @app.get("/hotspots/top")
# def get_hotspots_top(n: int = 5):
#     df = load_choropleth_df()  # same DF used for the map endpoint

#     # Score = (latest_forecast – latest_cases) or any growth metric
#     df["growth"] = df["latest_forecast"] - df["latest_cases"]

#     df_sorted = df.sort_values("growth", ascending=False).head(n)

#     return df_sorted[[
#         "name",
#         "latest_cases",
#         "latest_forecast",
#         "risk_level",
#         "growth"
#     ]].to_dict(orient="records")
