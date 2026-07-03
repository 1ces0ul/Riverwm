#!/bin/sh

set -eu

mode="${1:-full}"
state_dir="${XDG_RUNTIME_DIR:-/tmp}/river-screenrecord"
pidfile="${state_dir}/wf-recorder.pid"
pathfile="${state_dir}/wf-recorder.path"
logfile="${state_dir}/wf-recorder.log"
idfile="${state_dir}/wf-recorder.notification-id"
outputfile="${state_dir}/wf-recorder.output"
output_dir="${HOME}/Videos/Screenrecords"

send_notification() {
	urgency="$1"
	summary="$2"
	body="$3"
	if command -v notify-send >/dev/null 2>&1; then
		replace_id="$(cat "$idfile" 2>/dev/null || true)"
		case "$replace_id" in
			"" | *[!0-9]*)
				replace_id=""
				;;
		esac

		if [ -n "$replace_id" ] && [ -n "$urgency" ]; then
			new_id="$(notify-send -p -a screenrecord -r "$replace_id" -u "$urgency" "$summary" "$body" 2>/dev/null || true)"
		elif [ -n "$replace_id" ]; then
			new_id="$(notify-send -p -a screenrecord -r "$replace_id" "$summary" "$body" 2>/dev/null || true)"
		elif [ -n "$urgency" ]; then
			new_id="$(notify-send -p -a screenrecord -u "$urgency" "$summary" "$body" 2>/dev/null || true)"
		else
			new_id="$(notify-send -p -a screenrecord "$summary" "$body" 2>/dev/null || true)"
		fi

		case "$new_id" in
			"" | *[!0-9]*)
				;;
			*)
				printf '%s\n' "$new_id" > "$idfile"
				;;
		esac
	fi
}

notify() {
	send_notification "" "$1" "$2"
}

notify_critical() {
	send_notification "critical" "$1" "$2"
}

is_recorder_pid() {
	pid="$1"
	[ -n "$pid" ] || return 1
	[ -d "/proc/$pid" ] || return 1
	[ "$(ps -p "$pid" -o comm= 2>/dev/null)" = "wf-recorder" ]
}

file_body() {
	file="$1"
	output="${2-}"
	printf 'File: %s\nDir: %s' "$(basename "$file")" "$(dirname "$file")"
	if [ -n "$output" ]; then
		printf '\nOutput: %s' "$output"
	fi
}

failure_reason() {
	reason="$(tail -n 3 "$logfile" 2>/dev/null | tr '\n' ' ' | sed 's/[[:space:]]*$//' || true)"
	[ -n "$reason" ] && printf '%s' "$reason"
}

failure_body() {
	file="$1"
	output="${2-}"
	body="$(file_body "$file" "$output")"
	reason="$(failure_reason)"
	if [ -n "$reason" ]; then
		printf 'Reason: %s\n%s' "$reason" "$body"
	else
		printf '%s\nLog: %s' "$body" "$logfile"
	fi
}

enabled_outputs() {
	command -v wlr-randr >/dev/null 2>&1 || return 1
	wlr-randr 2>/dev/null | awk '
		function flush_output() {
			if (name != "" && enabled == "yes") {
				if (description == "") {
					description = name
				}
				gsub(/^"/, "", description)
				gsub(/"$/, "", description)
				print name "\t" description
			}
		}
		/^[^[:space:]]/ {
			flush_output()
			name = $1
			description = $0
			sub(/^[^[:space:]]+[[:space:]]*/, "", description)
			enabled = ""
			next
		}
		/^[[:space:]]+Enabled:/ {
			enabled = $2
			next
		}
		END {
			flush_output()
		}
	'
}

numbered_outputs() {
	awk -F '\t' '{printf "%d\t%s\t%s\n", NR, $1, $2}'
}

output_from_selection() {
	selection="$1"
	outputs="$2"
	index="$(printf '%s\n' "$selection" | awk '{print $1}')"

	case "$index" in
		"" | *[!0-9]*)
			printf '%s\n' "$outputs" | awk -F '\t' -v selected="$selection" '
				$1 == selected {
					print $1
					found = 1
					exit
				}
				END {
					exit found ? 0 : 1
				}
			'
			;;
		*)
			printf '%s\n' "$outputs" | awk -F '\t' -v target="$index" '
				NR == target {
					print $1
					found = 1
					exit
				}
				END {
					exit found ? 0 : 1
				}
			'
			;;
	esac
}

choose_capture_output() {
	if [ -n "${SCREENRECORD_OUTPUT:-}" ]; then
		printf '%s\n' "$SCREENRECORD_OUTPUT"
		return 0
	fi

	outputs="$(enabled_outputs || true)"
	if [ -z "$outputs" ]; then
		return 1
	fi

	if command -v fuzzel >/dev/null 2>&1; then
		selection="$(
			printf '%s\n' "$outputs" |
				numbered_outputs |
				fuzzel --dmenu --prompt "Record output: " --lines 8 --width 90
		)" || return 2
		[ -n "$selection" ] || return 2
		output_from_selection "$selection" "$outputs" || return 1
		return 0
	fi

	output_count="$(printf '%s\n' "$outputs" | sed '/^[[:space:]]*$/d' | wc -l)"
	if [ "$output_count" -eq 1 ]; then
		printf '%s\n' "$outputs" | awk -F '\t' '{print $1}'
		return 0
	fi

	return 1
}

stop_recording() {
	pid="$1"
	outfile="$(cat "$pathfile" 2>/dev/null || true)"
	capture_output="$(cat "$outputfile" 2>/dev/null || true)"

	if kill -INT "$pid" 2>/dev/null; then
		i=0
		while [ "$i" -lt 50 ] && kill -0 "$pid" 2>/dev/null; do
			sleep 0.1
			i=$((i + 1))
		done
		if kill -0 "$pid" 2>/dev/null; then
			notify_critical "Recording stop pending" "wf-recorder pid ${pid} did not exit after SIGINT"
			return
		fi
		rm -f "$pidfile" "$pathfile" "$outputfile"
		if [ -n "$outfile" ]; then
			notify "Recording stopped" "$(file_body "$outfile" "$capture_output")"
		else
			notify "Recording stopped" "File path unavailable"
		fi
	else
		rm -f "$pidfile" "$pathfile" "$outputfile"
		notify_critical "Recording stop failed" "Could not signal wf-recorder pid ${pid}"
	fi
}

mkdir -p "$state_dir" "$output_dir"

if [ -f "$pidfile" ]; then
	old_pid="$(cat "$pidfile" 2>/dev/null || true)"
	if is_recorder_pid "$old_pid"; then
		stop_recording "$old_pid"
		exit 0
	fi
	rm -f "$pidfile" "$pathfile" "$outputfile"
fi

running_pid="$(pgrep -x wf-recorder 2>/dev/null | sed -n '1p' || true)"
if is_recorder_pid "$running_pid"; then
	stop_recording "$running_pid"
	exit 0
fi

if ! command -v wf-recorder >/dev/null 2>&1; then
	notify_critical "Recording failed" "wf-recorder was not found"
	exit 1
fi

outfile="${output_dir}/$(date +%F_%H-%M-%S).mp4"
: > "$logfile"
capture_output=""

case "$mode" in
	full)
		chooser_status=0
		capture_output="$(choose_capture_output)" || chooser_status=$?
		if [ "$chooser_status" -eq 2 ]; then
			notify "Recording canceled" "No output selected"
			exit 0
		elif [ "$chooser_status" -ne 0 ] || [ -z "$capture_output" ]; then
			notify_critical "Recording failed" "Could not select an enabled output"
			exit 1
		fi
		wf-recorder -o "$capture_output" -f "$outfile" > "$logfile" 2>&1 &
		;;
	region)
		if ! command -v slurp >/dev/null 2>&1; then
			notify_critical "Recording failed" "slurp was not found"
			exit 1
		fi
		geometry="$(slurp || true)"
		if [ -z "$geometry" ]; then
			notify "Recording canceled" "No region selected"
			exit 0
		fi
		wf-recorder -g "$geometry" -f "$outfile" > "$logfile" 2>&1 &
		;;
	*)
		notify_critical "Recording failed" "Unknown mode: ${mode}"
		exit 1
		;;
esac

pid="$!"
printf '%s\n' "$pid" > "$pidfile"
printf '%s\n' "$outfile" > "$pathfile"
if [ -n "$capture_output" ]; then
	printf '%s\n' "$capture_output" > "$outputfile"
else
	rm -f "$outputfile"
fi

sleep 0.5
if is_recorder_pid "$pid"; then
	notify "Recording started" "$(file_body "$outfile" "$capture_output")"
else
	rm -f "$pidfile" "$pathfile" "$outputfile"
	notify_critical "Recording failed" "$(failure_body "$outfile" "$capture_output")"
	exit 1
fi
