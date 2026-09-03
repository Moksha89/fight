# RoosterRun SRS media plane

This template runs the media plane used by the streaming engine. It accepts
WHIP camera publishing, exposes WHEP playback, generates an HLS fallback, and
records hourly DVR segments.

1. Copy `.env.example` to `.env` and replace `CANDIDATE` with the droplet's
   public IPv4 address.
2. Start the compose project on the streaming host.
3. Allow UDP port 8000 through the droplet firewall. Keep ports 1985 and 8080
   bound to loopback and expose them through the site's HTTPS reverse proxy.
4. Configure the application process with:

   ```text
   ROOSTERRUN_WHIP_BASE_URL=https://your-domain.example
   ROOSTERRUN_WHEP_BASE_URL=https://your-domain.example
   ROOSTERRUN_HLS_BASE_URL=https://your-domain.example/media
   ROOSTERRUN_RECORDING_BASE_URL=https://your-domain.example/media/recordings
   ROOSTERRUN_RECORDING_EXTENSION=flv
   ROOSTERRUN_SRS_HOOK_SECRET=the-same-long-random-value-from-.env
   ```

5. Route `/rtc/` to SRS port 1985 and `/media/` to SRS port 8080. Camera access
   and WHIP publishing require HTTPS on real devices.

The admin streaming-health endpoint reports `configuration_required` until the
WHIP and WHEP base URLs are set. The engine adds a one-use 90-second publishing
ticket to the WHIP request and the authenticated SRS `on_publish` hook validates
it. SRS `on_dvr` callbacks register completed recording URLs, and the player
automatically retries failed WHEP sessions before using native HLS fallback.
Configure the reverse proxy to redact query strings from `/rtc/` and hook logs.

The configuration follows the official SRS WHIP/WHEP and WebRTC candidate
model: <https://github.com/ossrs/srs/blob/develop/trunk/conf/full.conf>.
