# HTML template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Dog Counter Detection</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #1a1a1a;
            color: #fff;
        }
        h1 {
            text-align: center;
            color: #4CAF50;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .video-container {
            text-align: center;
            margin: 20px 0;
        }
        img {
            max-width: 100%;
            border: 3px solid #4CAF50;
            border-radius: 8px;
        }
        .info {
            background-color: #2a2a2a;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .zone-list {
            list-style: none;
            padding: 0;
        }
        .zone-item {
            padding: 8px;
            margin: 5px 0;
            background-color: #333;
            border-radius: 4px;
        }
        .enabled {
            border-left: 4px solid #4CAF50;
        }
        .disabled {
            border-left: 4px solid #666;
            opacity: 0.5;
        }
        .polygon-coords {
            font-family: monospace;
            font-size: 0.85em;
            color: #aaa;
            margin-top: 5px;
        }
    </style>
</head>

<body>
    <div class="container">
        <h1>🐕 No Diggity - Calibration</h1>
        
        <div class="video-container" style="margin: 0px">
            <img id="video-stream" 
                 style="border: 0px" 
                 src="{{ url_for('video_feed') }}" 
                 alt="Video Stream">
        </div>

        <div id="coords"></div>
        
        <div class="info">
            <h3>Configured Zones:</h3>
            <ul class="zone-list">
                {% for zone_id, zone in zones.items() %}
                <li class="zone-item {{ 'enabled' if zone.enabled else 'disabled' }}">
                    <strong>{{ zone.name }}</strong> - 
                    {{ 'ACTIVE' if zone.enabled else 'DISABLED' }} - 
                    Action: {{ zone.action }}
                    <div class="polygon-coords">
                        Points: {{ zone.polygon }}
                    </div>
                </li>
                {% endfor %}
            </ul>
        </div>
        
        <div class="info">
            <h3>Instructions:</h3>
            <p>• <strong>White dots</strong> show polygon vertices for calibration</p>
            <p>• Adjust polygon points in the Python script ZONES config</p>
            <p>• Points should trace the outline of your counter/table</p>
            <p>• Green boxes = dog on floor (safe)</p>
            <p>• Red boxes = dog on counter (alert!)</p>
            <p>• Refresh page if stream stops</p>
        </div>
        
        <div class="info">
            <h3>Calibration Tips:</h3>
            <p>• Start with rough points, then fine-tune each vertex</p>
            <p>• Use at least 4 points per zone (more for complex shapes)</p>
            <p>• Points can be in any order (clockwise or counter-clockwise)</p>
            <p>• Watch the video to see if zones align with actual surfaces</p>
        </div>
    </div>

    <script>
        const videoStream = document.getElementById('video-stream');

        // Actual camera resolution
        const actualWidth = {{ video_width }};
        const actualHeight = {{ video_height }};

        videoStream.addEventListener('mousemove', (event) => {
            // Displayed resolution on the page
            const displayedWidth = videoStream.width;
            const displayedHeight = videoStream.height;

            // Calculate actual coordinates based on displayed resolution and 
            // actual resolution
            const actualX = Math.round(
                (event.offsetX / displayedWidth) * actualWidth
            );

            const actualY = Math.round(
                (event.offsetY / displayedHeight) * actualHeight
            );

            // Display the actual coordinates in the #coords element
            document.getElementById('coords').textContent = 
                `X: ${actualX}, Y: ${actualY}`;
        });
    </script>
</body>
</html>
"""
