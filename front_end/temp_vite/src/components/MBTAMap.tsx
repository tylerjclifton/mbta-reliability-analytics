import { MapContainer, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

const MBTA_CENTER = {
  lat: 42.3601,
  lng: -71.0589,
  zoom: 12
}

export function MBTAMap() {
  return (
    <MapContainer
      center={[MBTA_CENTER.lat, MBTA_CENTER.lng]}
      zoom={MBTA_CENTER.zoom}
      style={{ height: '100vh', width: '100%' }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
    </MapContainer>
  )
}