import requests

from kacky_eventpage_backend import config, secrets
from kacky_eventpage_backend.db_ops.db_base import DBConnection

TMX_PACK_ID = 10261488
EVENTTYPE = "KK"

if __name__ == "__main__":
    backend = DBConnection(config, secrets)

    if EVENTTYPE == "KK":
        queryurl = f"https://tmnf.exchange/api/tracks?packid={TMX_PACK_ID}&count=51&fields=TrackId,TrackName"
        r = requests.get(queryurl)

        tmx_insert_query = """
                           UPDATE maps INNER JOIN events
                               ON events.id = maps.kackyevent
                           SET tmx_id = ?
                           WHERE kacky_id = ? and events.type = "KK";
                           """
        for t in r.json()["Results"]:
            kid = t["TrackName"].split("#")[1].replace("–", "-")
            backend._cursor.execute(tmx_insert_query, (t["TrackId"], kid))
            # print(tmx_insert_query, (t["TrackId"], kid))
        backend._connection.commit()

    elif EVENTTYPE == "KR":
        api = "https://trackmania.exchange/api/tracks/get_track_info/uid/"
        uid_query = """
            SELECT maps.tm_uid
            FROM maps
            INNER JOIN events ON maps.kackyevent = events.id
            WHERE events.type = 'KR';
        """
        uids = backend.fetchall(uid_query, ())
        tmx_insert_query = "UPDATE maps SET tmx_id = ? WHERE tm_uid = ?;"
        for uid in uids:
            tmxid = requests.get(api + str(uid[0])).json()["TrackID"]
            if not tmxid.ok:
                print("Error getting data from TMX " + api + str(uid[0]))
                exit(1)
            backend._cursor.execute(tmx_insert_query, (tmxid, uid[0]))
        backend._connection.commit()
    else:
        print("bad EVENTTYPE!")
        exit(1)
