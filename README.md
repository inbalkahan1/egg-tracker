# Egg & Oil Tracker

Double-click Start_Tracker.bat. This is a standalone desktop application; no notebook kernel or SAM2 checkpoint is required. It uses the existing sam2-env Python installation on this computer.

1. Browse to your AVI. Choose the output Projects folder (choose a folder on your SSD if that is where you want results).
2. Set the approximate minimum and maximum egg radius in ORIGINAL video pixels. Defaults 15–65 are starting values, not calibrated for every video. Lower detection threshold finds more circles and more false positives. Choose gravity direction; Down is the usual setting.
3. Start automatic tracking. Every frame is scanned through the end of the video. Stop and save retains the processed portion. The original AVI is unchanged.
4. Review opens when processing/export finishes. Select a track from the longest-first list. All tracks are included by default; the minimum-detections filter changes the list only, not exported data.
5. Correct egg circle or Correct oil circle: click CENTER then EDGE, preferably in the enlarged view. These are independent perfect circles. Accept frame only when both are correct; rejected measurements have no angle in Excel. Clear oil removes an uncertain globule.
6. From a corrected frame, Re-track next 50 automatic frames replaces automatic proposals ahead, stopping before manual/reviewed records or an uncertain detection. Undo edit reverses this batch. Track forward extends into frames without existing records. It pauses when egg or oil is uncertain.
7. Split track here and Merge non-overlapping tracks repair fragmented or switched identities. New ID allows a missed egg to be drawn and tracked. Reject track excludes a false detection from Excel if all its frames are rejected.
8. Save, then Export ALL eggs to Excel (or selected egg). Close the destination workbook in Excel before exporting again. Open saved project chooses its session.json and restores circles for further editing.

## Outputs
Each run creates a new dated project folder under EggOilTracker/projects by default:
- session.json: editable tracking results. Keep this and project.json together with access to the original video.
- automatic_original.json: untouched initial automatic results.
- measurements.csv: per-record center measurements.
- egg_angles.xlsx: Summary plus a sheet per candidate egg ID, with rows for every frame between its first and last observed center. Gaps stay blank. Export selected egg creates egg_ID_angles.xlsx.
- project.json: video settings and gravity direction.
- run_status.json: processing progress and status.

Excel includes original zero-based frame number, clip time, egg/oil center X and Y, radii, signed angle, reviewed angle, and review/focus flags. Signed angle contains automatic or edited estimates. Reviewed angle contains only accepted measurements. Unchecking Include unreviewed candidate tracks limits export to IDs with at least one accepted frame; unaccepted rows remain labeled and reviewed angles blank.

Coordinates use the upper-left image origin, X right, Y down. For downward gravity: 0 degrees means oil above egg center, positive to the right, negative to the left, and 180 degrees directly below. General calculation is atan2(clockwise component, opposite-gravity component). Centers separated by less than one pixel have no angle. This is the 2D projected angle; it does not recover a 3D orientation.

Automatic detection proposes circular eggs and internal oil globules; it cannot guarantee every egg or correct identity in every frame. Review faint globules, overlaps, boundary clipping, and track fragments. Focus is manually labeled and no continuous-focus duration filter is imposed. Excel edits do not feed back into the tracker; make tracking corrections in the review window and re-export.

## VS Code
Open tracker.py and select C:\Users\camera\Documents\masking\sam2-env\python.exe as interpreter, then Run Python File. Alternatively use Start_Tracker.bat.

Excel export uses the bundled Node/artifact-tool runtime installed on this computer. The folder's node_modules link points to that runtime. Moving this app to another computer requires installing Python dependencies (numpy, opencv-python, Pillow, tkinter) and configuring the Excel runtime.

## Validation
Tested on a generated 12-frame circle video: egg and oil detections present in every frame; review open/save succeeds. Spreadsheet formulas were checked against independent signed-angle calculations, including missing and coincident centers. This validates the workflow, not detection accuracy on a new experimental video.

## Reviewed frame image folders
In the review window, use **Export frame images (50+ edited / accepted)**. The current edits are saved first. Each egg with at least 50 distinct frames currently marked edited or accepted (and an egg circle) gets its own folder. The frames need not be consecutive; a frame counts once. Automatic, rejected and missing frames are excluded. Missing oil is labeled unavailable rather than invented.

Output: a new `reviewed_frame_images_DATE_TIME/egg_ID` folder inside the current project, containing full-resolution PNG frames with green egg circles, orange oil circles, a white zero-reference arrow (opposite gravity), source frame number, status, and signed angle. A manifest records the exported frame numbers. Repeating the export creates a new folder and preserves earlier exports. Edited does not mean accepted: review status remains visible. Restart the tracker to load this new button.
