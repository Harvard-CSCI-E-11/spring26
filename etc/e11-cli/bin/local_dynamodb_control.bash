#!/usr/bin/env bash
set -e
#
# Run or Stop DynamoDBLocal on both Linux and MacOS
# Assumes DynamoDB installed in the root directory

MYDIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOGDIR="$(dirname $MYDIR)/logs"
DBDIR="$(dirname $MYDIR)/var"
FLAGS="-sharedDb -dbPath $DBDIR -port 8010"
PIDFILE="$DBDIR/dynamodb_local.pid"

command -v java > /dev/null || { echo "Java not found in PATH. Aborting."; exit 1; }

mkdir -p "$LOGDIR" "$DBDIR"

wait_dynamodb_local() {
    # Wait for port 8010 to be accepting connections
    for i in {1..30}; do
        if curl -s http://localhost:8010/ > /dev/null; then
            echo "DynamoDB Local is ready."
            break
        fi
        echo "  Waiting for DynamoDBLocal to be ready ($i)..."
        sleep 1
    done
}

# Function to start DynamoDB Local
start_dynamodb_local() {
    # Check if DynamoDBLocal is already running
    if pgrep -f "DynamoDBLocal.jar" > /dev/null
    then
        wait_dynamodb_local
        echo "DynamoDB Local is already running."
        exit 0
    fi

    # Set JAVA_HOME dynamically for macOS using Homebrew
    if [ "$(uname -s)" = 'Darwin' ]; then
        export JAVA_HOME="$(brew --prefix openjdk)"
        export PATH="$JAVA_HOME/bin:$PATH"
    fi

    # Run DynamoDB Local in the background, redirecting output
    echo "Starting DynamoDB Local..."
    java -Djava.library.path="$MYDIR/DynamoDBLocal_lib" -jar "$MYDIR/DynamoDBLocal.jar" \
         $FLAGS > "$LOGDIR/dynamodb_local.stdout" 2> "$LOGDIR/dynamodb_local.stderr" &
    echo $! > "$PIDFILE"

    wait_dynamodb_local
    echo "DynamoDB Local started in the background (PID: $!)."
    echo "DynamoDB Local endpoint: http://localhost:8010"
}

# Function to stop DynamoDB Local
stop_dynamodb_local() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat $PIDFILE)
        if ps -p $PID > /dev/null; then
            echo "Stopping DynamoDB Local (PID: $PID)..."
            kill $PID
            # Give it a moment to shut down gracefully
            sleep 2
            if ps -p $PID > /dev/null; then
                echo "DynamoDB Local (PID: $PID) did not shut down gracefully. Forcing kill."
                kill -9 $PID # Force kill if it's still running
            fi
            rm -f "$PIDFILE"
            echo "DynamoDB Local stopped."
        else
            echo "PID file exists but DynamoDB Local (PID: $PID) is not running. Removing stale PID file."
            rm -f "$PIDFILE"
        fi
    else
        echo "No $PIDFILE file found. Checking for running process with pgrep."
        PID=$(pgrep -f "DynamoDBLocal.jar" || exit 0)
        if [ -n "$PID" ]; then
            echo "Found running DynamoDB Local (PID: $PID) using pgrep. Stopping..."
            kill $PID
            sleep 2
            if ps -p $PID > /dev/null; then
                echo "DynamoDB Local (PID: $PID) did not shut down gracefully. Forcing kill."
                kill -9 $PID
            fi
            echo "DynamoDB Local stopped."
        else
            echo "DynamoDB Local is not running."
        fi
    fi
}

# Main script logic
case "$1" in
    start)
        start_dynamodb_local
        ;;
    stop)
        stop_dynamodb_local
        ;;
    restart)
        stop_dynamodb_local
        start_dynamodb_local
        ;;
    status)
        if pgrep -f "DynamoDBLocal.jar" > /dev/null
        then
            echo "DynamoDB Local is running."
        else
            echo "DynamoDB Local is not running."
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac

exit 0
