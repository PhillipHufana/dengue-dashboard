@router.get("/data/info")
def get_data_info():
    sb = get_supabase()

    # Find the latest historical case week
    latest = (
        sb.table("barangay_weekly")
        .select("week_start")
        .order("week_start", desc=True)
        .limit(1)
        .execute()
        .data
    )

    last_update = latest[0]["week_start"] if latest else None

    return {
        "last_historical_date": last_update,
        "server_date": datetime.now().strftime("%Y-%m-%d")
    }
