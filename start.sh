#!/bin/bash
# Start Bokeh server on Render
bokeh serve main.py --allow-websocket-origin='*' --port $PORT
