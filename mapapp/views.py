from django.shortcuts import render
from django.http import JsonResponse
import folium, requests, os
from dotenv import load_dotenv
from folium import Html, Element
import overpy
import math

load_dotenv()
ORS_API_KEY = os.getenv("ORS_API_KEY")

def snap_to_road(lat, lon, profile="cycling-road"):
    """Return nearest routable coordinate for the given point."""
    url = f"https://api.openrouteservice.org/v2/snap/{profile}"
    headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
    body = {"locations": [[float(lon), float(lat)]]}

    try:
        r = requests.post(url, headers=headers, json=body, timeout=10)
        r.raise_for_status()
        data = r.json()

        # Some profiles (especially cycling) return no result in remote areas
        locs = data.get("locations")
        if not locs or not locs[0].get("location"):
            print("⚠️  Snap failed — using original coordinates")
            return lat, lon

        snapped = locs[0]["location"]  # [lon, lat]
        return snapped[1], snapped[0]  # (lat, lon)

    except Exception as e:
        print(f"⚠️  Snap request failed: {e}")
        return lat, lon



def map_view(request):
    """Render interactive drive-time map centred on Sherborne."""
    lat0, lon0 = 50.9495, -2.5177
    m = folium.Map(location=[lat0, lon0], zoom_start=10, tiles="CartoDB positron")

    folium.LatLngPopup().add_to(m)

    # --- Inject JavaScript directly into the map iframe ---
    js_code = """
  <script>
    document.addEventListener("DOMContentLoaded", function() {
        // find the real map variable Folium created
        var mapobj = Object.values(window).find(v => v instanceof L.Map);
        if (!mapobj) {
            console.error("No Leaflet map object found");
            return;
        }

        console.log("Isochrone click handler attached");

        function drawIsochrones(data) {
            if (mapobj._driveLayers) mapobj._driveLayers.forEach(l => mapobj.removeLayer(l));
            mapobj._driveLayers = [];
            (data.features || []).forEach(f => {
                var mins = f.properties.value / 60;
                var color = (mins === 30) ? 'green' : (mins === 60) ? 'orange' : 'red';
                var layer = L.geoJSON(f.geometry, { color: color, weight: 2, fill: false });
                layer.addTo(mapobj);
                mapobj._driveLayers.push(layer);
            });
        }

        function handleClick(e) {
            if (mapobj._clickMarker) mapobj.removeLayer(mapobj._clickMarker);
            mapobj._clickMarker = L.marker(e.latlng)
                .addTo(mapobj)
                .bindPopup("Ride from here")
                .openPopup();

            const profiles = [
                { mode: "cycling-regular", color: "green", label: "2 W/kg YAG" },
                { mode: "cycling-road", color: "blue", label: "3 W/kg" }
            ];

            // Remove any previous polygons
            if (mapobj._driveLayers) mapobj._driveLayers.forEach(l => mapobj.removeLayer(l));
            mapobj._driveLayers = [];

            profiles.forEach(p => {
                fetch(`/iso/?lat=${e.latlng.lat}&lon=${e.latlng.lng}&mode=${p.mode}`)
                    .then(r => r.json())
                    .then(data => {
                        if (!data.features) return;
                        data.features.forEach(f => {
                            const layer = L.geoJSON(f.geometry, {
                                color: p.color,
                                weight: 2,
                                fill: false
                            }).addTo(mapobj);
                            layer.bindPopup(`${p.label} cyclist (${p.mode})`);
                            mapobj._driveLayers.push(layer);
                        });
                    })
                    .catch(err => console.error(`Isochrone fetch failed for ${p.mode}`, err));
            });
        }

        mapobj.on('click', handleClick);

        const legend = L.control({ position: "bottomright" });
        legend.onAdd = function () {
            const div = L.DomUtil.create("div", "info legend");
            div.innerHTML = `
                <b>Cycling 1 h range</b><br>
                <i style="background-color:green;">---</i> 2 W/kg (YAG)<br>
                <i style="background-color:blue;">---</i> 3 W/kg<br>
                `;

            return div;
        };
        legend.addTo(mapobj);

        console.log("Legend added");
    });
    </script>

    """

    m.get_root().html.add_child(Element(js_code))

    return render(request, "mapapp/map.html", {"map": m._repr_html_()})

def old_map_view(request):
    """Render interactive drive-time map centred on Sherborne."""
    lat0, lon0 = 50.9495, -2.5177
    m = folium.Map(location=[lat0, lon0], zoom_start=10, tiles="CartoDB positron")

    folium.LatLngPopup().add_to(m)

    # --- Inject JavaScript directly into the map iframe ---
    js_code = """
    <script>
    document.addEventListener("DOMContentLoaded", function() {
        // Folium sets a map variable like "map_xxxxx"
        var mapobj = Object.values(window)
            .find(v => v instanceof L.Map);
        if (!mapobj) { console.error("No Leaflet map object found"); return; }

        function drawIsochrones(data) {
            if (mapobj._driveLayers) mapobj._driveLayers.forEach(l => mapobj.removeLayer(l));
            mapobj._driveLayers = [];
            (data.features || []).forEach(f => {
                var mins = f.properties.value / 60;
                var color = (mins === 30) ? 'green' : (mins === 60) ? 'orange' : 'red';
                var layer = L.geoJSON(f.geometry, {color: color, weight: 2, fill: false});
                layer.addTo(mapobj);
                mapobj._driveLayers.push(layer);
            });
        }

        function handleClick(e) {
            if (mapobj._clickMarker) mapobj.removeLayer(mapobj._clickMarker);
            mapobj._clickMarker = L.marker(e.latlng)
                .addTo(mapobj)
                .bindPopup("Cycling isochrones from here (1 h)")
                .openPopup();

            const profiles = [
                { mode: "cycling-regular", color: "green", label: "2W/kg" },
                { mode: "cycling-road", color: "red", label: "3W/kg" },            ];

            // Remove any previous polygons
            if (mapobj._driveLayers) mapobj._driveLayers.forEach(l => mapobj.removeLayer(l));
            mapobj._driveLayers = [];

            profiles.forEach(p => {
                fetch(`/iso/?lat=${e.latlng.lat}&lon=${e.latlng.lng}&mode=${p.mode}`)
                .then(r => r.json())
                .then(data => {
                    if (!data.features) return;
                    data.features.forEach(f => {
                        const layer = L.geoJSON(f.geometry, {
                            color: p.color,
                            weight: 2,
                            fill: false
                        }).addTo(mapobj);
                        layer.bindPopup(`${p.label} cyclist (${p.mode})`);
                        mapobj._driveLayers.push(layer);
                    });
                })
                .catch(err => console.error(`Isochrone fetch failed for ${p.mode}`, err));
            });
        }



        mapobj.on('click', handleClick);
        console.log("Isochrone click handler attached");
    });
    </script>
    """

    m.get_root().html.add_child(Element(js_code))

    return render(request, "mapapp/map.html", {"map": m._repr_html_()})


def get_isochrones(request):
    lat = float(request.GET.get("lat"))
    lon = float(request.GET.get("lon"))
    mode = request.GET.get("mode", "cycling-road")
    rng = float(request.GET.get("range", 3600))

    try:
        # 🚴 scale distance for cycling-road
        if mode == "cycling-road":
            rng *= 1.2    # go 20% farther in same time (simulate faster rider)

        # Snap first
        snapped_lat, snapped_lon = snap_to_road(lat, lon, profile=mode)
        print(f"Snapped from ({lat:.5f},{lon:.5f}) → ({snapped_lat:.5f},{snapped_lon:.5f})")

        url = f"https://api.openrouteservice.org/v2/isochrones/{mode}"
        headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
        body = {"locations": [[snapped_lon, snapped_lat]], "range": [rng]}

        r = requests.post(url, headers=headers, json=body, timeout=20)
        r.raise_for_status()
        return JsonResponse(r.json())

    except Exception as e:
        import traceback; traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)




def get_facilities(request):
    """Return GP surgeries, clinics and hospitals within ~1h (≈50 km) of the clicked point."""
    lat = float(request.GET.get("lat"))
    lon = float(request.GET.get("lon"))
    print(f"🏥 Fetching facilities near {lat},{lon}")

    # Roughly 0.45° ≈ 50 km in the UK
    lat_delta = 0.45
    lon_delta = 0.7 / math.cos(math.radians(lat))  # shrink E–W with latitude
    lat_min, lat_max = lat - lat_delta, lat + lat_delta
    lon_min, lon_max = lon - lon_delta, lon + lon_delta

    try:
        api = overpy.Overpass()
        query = f"""
        [out:json][timeout:25];
        (
          node["amenity"="doctors"]({lat_min},{lon_min},{lat_max},{lon_max});
          node["amenity"="clinic"]({lat_min},{lon_min},{lat_max},{lon_max});
          node["amenity"="hospital"]({lat_min},{lon_min},{lat_max},{lon_max});
        );
        out center;
        """
        result = api.query(query)
        print(f"Found {len(result.nodes)} facilities")

        # Build GeoJSON
        features = []
        for node in result.nodes:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [node.lon, node.lat]},
                "properties": {
                    "name": node.tags.get("name", "Unnamed"),
                    "amenity": node.tags.get("amenity", "healthcare")
                },
            })
        return JsonResponse({"type": "FeatureCollection", "features": features})
    except Exception as e:
        import traceback; traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)
