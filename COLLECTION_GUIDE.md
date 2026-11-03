# One frame per egg collection

Start_Collection.bat opens the shared collection. Results default to:
F:\Inbal\EGG TRACKER\angle_collection

## New videos, one at a time
1. Open Start_Tracker.bat and Browse to your AVI.
2. Either run automatic tracking, or choose "Open chosen AVI for manual review" to start immediately without scanning the video.
3. Use a separate New ID for each physical egg. Navigate to a focused frame, draw/correct the egg and oil circles, mark Focus: Clear, and Accept frame. If you review several frames for that egg, the collection can choose randomly among them.
4. Save, then "Collect one frame per egg". In the collection, uncheck inclusion of unassessed focus when you want strictly Clear-only sampling. A frame must be edited or accepted, have both valid circles with oil inside the egg, and must not be marked blurred.
5. Inspect the original crop and annotated crop. Confirm focused + distinct egg if accurate. Exclude duplicate / poor frame removes a sample from the distribution but retains its record.
6. Close the tracker review window when done. Choose another AVI and repeat, using the SAME collection folder. Each project remains editable.

## Existing projects
Choose saved project and select its session.json, or use the collection button inside the tracker. Existing source tracks retain their selected frame on reimport. Old edited/accepted frames with unassessed focus are included by request; this is explicitly recorded and never called focus-confirmed automatically. This importer supports the current and preceding standalone circle-detector session.json format. Older notebook CSV-only exports are not silently labeled reviewed.

## Random selection and independence
Initial selection is uniform among eligible reviewed frames for each source track, independent of angle. The random seed and selected source frame are stored. This is conditional sampling from your reviewed frames, not a random sample of all eggs in the experiment.
A track ID is not proof of a different biological egg. Potential duplicate analyses with closely matching egg circles at a shared frame are initially excluded. Disjoint track fragments, reappearing eggs and different video clips may still represent the same egg: use your experimental knowledge to exclude duplicates. Only confirm distinct identity after checking.
Reject frame; sample another draws from the remaining eligible frames and records the rejected frame and selection history. Use it for focus or annotation failure, not to obtain a preferred angle. If no alternatives are available, review more frames in the original project.
If you correct the selected frame in the tracker, save there, then Reload corrected frame in the collection. This refreshes its centers and images and clears the collection confirmation. Source projects themselves are never edited by the collector.

## Saved outputs
- collection.json: master sample list, selection history, seed, exclusions and confirmations.
- images/egg_sample_NNN/raw.png: original full-resolution frame.
- images/egg_sample_NNN/circles.png: egg/oil circles, reference arrow, sample ID, angle and source frame.
- Revised image files preserve earlier images when a sample is corrected/replaced.
- egg_angle_collection.xlsx: one row per sample, full source paths, frame, centers, radii, signed angle, review/focus/identity flags and clickable image paths. Excluded rows remain labeled for audit.
- Summary: progress toward 100 confirmed focused/distinct eggs and a 30-degree-bin distribution for all included samples and the confirmed subset separately. Counts/charts are snapshots refreshed on collection export; spreadsheet edits do not update the app.

Zero degrees is opposite gravity. With gravity downward, up=0, right=+90, left=-90, below=180. The quantity is a 2D projected angle.

Close the workbook in Excel before saving updates. Use one collection window at a time; stale-window saves are rejected. Collection data and images are saved even when Excel is open and blocks workbook replacement. Press Save Excel after closing it.

The spreadsheet exporter uses the bundled Python/openpyxl fallback because the bundled artifact-tool entry point is missing on this computer. The existing main tracker's separate Excel exporter is not used by the collector.

