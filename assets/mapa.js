// Funciones que dash-leaflet usa para dibujar los puntos del mapa.
// Se referencian desde Python como {"variable": "geovisor.pin"} y {"variable": "geovisor.grupo"}.
window.geovisor = {
  // Pin tipo Google Maps; el seleccionado es más grande y más oscuro
  pin: function (feature, latlng, context) {
    const sel = feature.properties.seleccionado;
    const color = sel ? "#B3261E" : context.hideout.color;
    const s = sel ? 1.3 : 1;
    const w = 26 * s, h = 38 * s;
    const svg =
      `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 26 38">` +
      `<path d="M13 0C5.8 0 0 5.8 0 13c0 9.7 13 25 13 25s13-15.3 13-25C26 5.8 20.2 0 13 0z" ` +
      `fill="${color}" stroke="#ffffff" stroke-width="1.5"/>` +
      `<circle cx="13" cy="13" r="4.6" fill="#ffffff"/></svg>`;
    const icon = L.divIcon({ html: svg, className: "pin", iconSize: [w, h], iconAnchor: [w / 2, h],
                             tooltipAnchor: [w / 2, -h * 0.7] });
    const m = L.marker(latlng, { icon: icon, keyboard: true, title: feature.properties.nombre });
    m.bindTooltip(feature.properties.ventana, { className: "ventana", direction: "auto", sticky: false });
    return m;
  },
  // Grupo de municipios cercanos (al alejar el mapa)
  grupo: function (feature, latlng, index, context) {
    const n = feature.properties.point_count;
    const s = n < 20 ? 34 : (n < 100 ? 42 : 52);
    const c = context.hideout.color;
    const icon = L.divIcon({
      html: `<div style="width:${s}px;height:${s}px;background:${c};box-shadow:0 0 0 5px ${c}40">${n}</div>`,
      className: "grupo", iconSize: [s, s] });
    return L.marker(latlng, { icon: icon, title: `${n} municipios` });
  }
};
