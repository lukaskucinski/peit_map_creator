# Leaflet Map Rendering Issue Investigation

## Problem Description

Some generated maps display with rendering issues:
- **Blank/white map**: Entire map area is white, only UI controls visible
- **Clipped layers**: Polygon and line layers are cut off or partially rendered
- **Side panel glitches**: Panel sections vanish, especially on hover

### Key Observation
**The issue consistently fixes itself when the user manually zooms in and then out.** This is the most important clue for diagnosing the root cause.

### Frequency
Affects a small minority of maps. The issue appears to be intermittent and may be related to specific geographic areas or layer complexity.

### Environment
- Happens in multiple browsers (Chrome, Firefox, Edge)
- Happens both on live Vercel URLs AND downloaded ZIP files opened locally
- This rules out Vercel caching as the cause - the issue is in the generated HTML itself

---

## Hypotheses

### 1. Leaflet SVG Renderer Initialization Race Condition (Most Likely)
Leaflet's SVG renderer may not complete the initial render due to:
- Map container size not fully calculated at initialization time
- Race condition between map initialization and layer rendering
- All tiles/layers not finished loading before first paint

**Evidence**: Zooming triggers Leaflet's internal redraw mechanisms, which fixes the issue.

### 2. Complex Geometry Overload
Initially suspected FEMA Flood Hazard Zones layer (very complex polygons with many vertices) was overwhelming the SVG renderer.

**Evidence Against**: Disabling the FEMA layer did not fix the issue.

### 3. CSS/Container Sizing Issue
The map container may not have valid dimensions when Leaflet initializes.

**Evidence**: `invalidateSize()` alone did not fix the issue, suggesting the container size is correct but the render itself is incomplete.

### 4. Folium/Leaflet Version Incompatibility
Potential incompatibility between Folium's generated HTML and the Leaflet version being used.

**Not Yet Tested**

---

## What We Tried

### Attempt 1: `invalidateSize()` Call
**Approach**: Call `map.invalidateSize({animate: false})` after map initialization to force Leaflet to recalculate container dimensions.

**Implementation**:
```javascript
if (window.mapObject && window.mapObject.invalidateSize) {
    window.mapObject.invalidateSize({animate: false});
}
```

**Result**: Did not fix the issue.

**Why It Failed**: `invalidateSize()` only applies changes when the container size has actually changed. If the container was always the correct size, this does nothing to force a layer redraw.

### Attempt 2: Multiple Delayed `invalidateSize()` Calls
**Approach**: Call `invalidateSize()` at multiple delays (600ms, 1000ms, 2000ms) to catch late-loading issues.

**Result**: Did not fix the issue.

**Why It Failed**: Same as above - the issue isn't container size, it's layer rendering.

### Attempt 3: Micro-Zoom Trick (0.1 zoom level)
**Approach**: Programmatically zoom in by 0.1 then immediately zoom back, to simulate the manual zoom that fixes the issue.

**Implementation**:
```javascript
var currentZoom = window.mapObject.getZoom();
var currentCenter = window.mapObject.getCenter();
window.mapObject.setZoom(currentZoom + 0.1, {animate: false});
setTimeout(function() {
    window.mapObject.setView(currentCenter, currentZoom, {animate: false});
}, 50);
```

**Result**: Did not fix the issue.

**Why It Failed**: A 0.1 zoom change may not be enough to trigger Leaflet's full redraw mechanism. Leaflet may optimize away such small changes.

### Attempt 4: Full Zoom Cycle (1 zoom level)
**Approach**: Zoom in by 1 full level then back, making the change perceptible.

**Implementation**:
```javascript
window.mapObject.setZoom(currentZoom + 1, {animate: false});
setTimeout(function() {
    window.mapObject.setView(currentCenter, currentZoom, {animate: false});
}, 100);
```

**Result**: Did not fix the issue. The zoom was visible (map jumped) but rendering issue persisted.

**Why It Failed**: Unknown. This should have triggered the same redraw as manual zooming. Possible reasons:
- The programmatic zoom doesn't trigger the exact same code path as user-initiated zoom
- Something about the timing or event sequence is different
- The issue may occur AFTER our JavaScript runs

### Attempt 5: Disable FEMA Flood Layer
**Approach**: Add `"enabled": false` to the FEMA Flood Hazard Zones layer config to test if complex geometries were the cause.

**Result**: Did not fix the issue.

**Why It Failed**: The issue is not related to geometry complexity.

---

## Potential Avenues to Explore

### 1. Canvas Renderer Instead of SVG
Leaflet supports both SVG and Canvas renderers. Canvas may handle complex scenes better.

```javascript
var map = L.map('map', {
    preferCanvas: true
});
```

**Pros**: May avoid SVG rendering bugs entirely
**Cons**: Requires changes to Folium map initialization; may affect layer styling

### 2. Fire Leaflet Events Directly
Instead of calling `setZoom()`, try firing the events that zoom triggers:

```javascript
window.mapObject.fire('zoomend');
window.mapObject.fire('moveend');
window.mapObject.fire('viewreset');
```

### 3. Force SVG Redraw via DOM Manipulation
Access the SVG element directly and force a repaint:

```javascript
var svg = document.querySelector('.leaflet-overlay-pane svg');
if (svg) {
    svg.style.display = 'none';
    svg.offsetHeight; // Force reflow
    svg.style.display = '';
}
```

### 4. Use `requestAnimationFrame` for Timing
The issue might be timing-related. Use `requestAnimationFrame` to ensure the browser is ready:

```javascript
requestAnimationFrame(function() {
    requestAnimationFrame(function() {
        // Redraw logic here
    });
});
```

### 5. Investigate User-Initiated vs Programmatic Zoom
Research why manual zoom works but programmatic doesn't:
- Check if there are different event handlers for user vs programmatic zoom
- Look for `_userInteraction` flags in Leaflet source

### 6. Delay Map Initialization
Instead of creating the map immediately, wait for all resources to load:

```javascript
window.addEventListener('load', function() {
    setTimeout(function() {
        // Initialize map here
    }, 500);
});
```

### 7. Check for CSS Conflicts
Inspect affected maps for:
- `overflow: hidden` on parent containers
- `transform` properties that might affect SVG rendering
- `will-change` or `contain` CSS properties

### 8. Compare Working vs Broken Maps
Do a detailed diff between a working map's HTML and a broken map's HTML to identify any differences in:
- Layer order
- Number of features
- Specific CSS classes applied
- JavaScript initialization timing

---

## Research Resources

### Leaflet GitHub Issues
- [Auto-detect changes to map size (invalidateSize) #941](https://github.com/Leaflet/Leaflet/issues/941)
- [Map not rendering correctly on load, but fine on viewport resize #8795](https://github.com/Leaflet/Leaflet/discussions/8795)
- [How to deal with maps loaded but hidden on current page? #2738](https://github.com/Leaflet/Leaflet/issues/2738)
- [Map tiles not loading until a zoom is executed #3002](https://github.com/Leaflet/Leaflet/issues/3002)
- [Vector layers are not redrawn while zooming #6409](https://github.com/Leaflet/Leaflet/issues/6409)
- [Zooming does not trigger a redraw #899](https://github.com/Leaflet/Leaflet/issues/899)

### Leaflet Documentation
- [Leaflet Reference - Map Methods](https://leafletjs.com/reference.html)
- [Leaflet Zoom Levels Tutorial](https://leafletjs.com/examples/zoom-levels/)

### Related Discussions
- [Display problem with Leaflet map in Bootstrap accordion (Drupal)](https://www.drupal.org/project/leaflet/issues/2845418)
- [Leaflet map doesn't render properly in stepper (MDBootstrap)](https://mdbootstrap.com/support/angular/leaflet-map-doesnt-render-properly-in-stepper/)

### Key Insights from Research
1. "If your Leaflet map suddenly works correctly after you resize your browser window, then you experience the classic 'map container size not valid at map initialization'"
2. "Vector layers are only redrawn after zooming is done - before that they are just zoomed in as-is" - this is by design
3. `invalidateSize()` "only applies any changes when the container size changed, which it didn't"
4. Future Leaflet releases may fix this automatically (PR #8612)

---

## Next Steps

1. **Reproduce consistently**: Find a specific input geometry that always causes the issue
2. **Browser DevTools investigation**:
   - Check computed styles on map container
   - Monitor network requests during load
   - Profile JavaScript execution timing
3. **Try Canvas renderer**: Modify Folium initialization to use Canvas instead of SVG
4. **Fire events directly**: Test if firing `viewreset`/`zoomend` events works
5. **Create minimal reproduction**: Strip down a broken map to minimal HTML to isolate the cause
