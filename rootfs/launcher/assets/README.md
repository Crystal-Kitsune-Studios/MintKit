# MintKit launcher assets

## setup.ogg

First-boot installer music, played by `mintsetup.py` behind the
`MINTSETUP_AUDIO` gate.

- Title: "Windows XP Installation Music - GRG Remix"
- Artist: GRG Productions Music
- Arrangement: GRG
- Source composition: "Velkommen" by Stan LePard
- Reference: https://www.youtube.com/watch?v=iaur86FNTYM

Used with credit, as the track's stated usage policy requires. The policy
also notes a marginal risk of a copyright claim, since this is an
arrangement rather than an original composition.

Encoded from the source mp3 with:

    ffmpeg -y -i source.mp3 -vn -map 0:a:0 -c:a libvorbis -q:a 3 \
      -ar 44100 -ac 2 setup.ogg

The `-vn -map 0:a:0` is required: the source carries embedded cover art,
and ffmpeg will otherwise re-encode it into a Theora video stream.
