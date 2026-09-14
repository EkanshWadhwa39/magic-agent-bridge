# magic_bridge.tcl
#
# Source this INSIDE an already-running Magic tkcon session:
#     source /path/to/magic_bridge.tcl
#
# Opens a plain TCP socket on localhost that executes whatever text line
# it receives as a Tcl command in Magic's own interpreter - i.e. exactly
# as if you'd typed it at tkcon - and sends the result back.
#
# This runs inside Magic's existing Tcl event loop (the same one driving
# the GUI), so it does NOT block the layout window or require any extra
# threads. Deliberately avoids `tk send` / X11 interp registration, since
# that mechanism is flaky on setups with two X11 stacks loaded at once
# (Homebrew cairo + XQuartz - a known crash source on this machine).
#
# SECURITY NOTE: this evaluates arbitrary Tcl in Magic's process with no
# auth. Binds to 127.0.0.1 only (not 0.0.0.0) so it's unreachable from
# the network - but any local process/user on this machine could still
# connect. Fine for a solo dev machine; do not run this on a shared box
# or expose the port beyond loopback.

if {[info exists ::magic_bridge_port] == 0} {
    set ::magic_bridge_port 5566
}

proc magic_bridge_accept {sock addr port} {
    fconfigure $sock -buffering line -blocking 0 -translation lf
    fileevent $sock readable [list magic_bridge_handle $sock]
}

proc magic_bridge_handle {sock} {
    if {[eof $sock]} {
        catch {close $sock}
        return
    }
    set cmd [gets $sock]
    if {$cmd eq ""} { return }

    set status [catch {uplevel #0 $cmd} output]
    # Single-line framed response: first token is OK or ERR, rest is payload.
    # Embedded newlines in $output are escaped so the response stays one line.
    set escaped [string map {"\n" "\\n"} $output]
    if {$status == 0} {
        puts $sock "OK $escaped"
    } else {
        puts $sock "ERR $escaped"
    }
    flush $sock
}

set ::magic_bridge_srv [socket -server magic_bridge_accept $::magic_bridge_port]
puts "magic_bridge: listening on 127.0.0.1:$::magic_bridge_port"
puts "magic_bridge: to stop, run: close \$::magic_bridge_srv"
