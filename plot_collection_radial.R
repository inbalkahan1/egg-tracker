# Egg/oil angle distribution: 0 up, +90 right, -90 left, +/-180 down.
# Open in RStudio and run the whole script. Change settings here.
input_file <- "F:/Inbal/EGG TRACKER/angle_collection/egg_angle_collection.xlsx"
sheet_name <- "Egg samples"
confirmed_only <- FALSE  # TRUE = focus Clear AND distinct egg confirmed.
bin_width_deg <- 30      # Must divide 360, e.g. 10, 15, 20, 30, 45.
show_individual_ticks <- TRUE
output_dir <- dirname(input_file)
# To choose another workbook interactively, use:
# input_file <- file.choose()
# output_dir <- dirname(input_file)

if (!requireNamespace("readxl", quietly = TRUE)) {
  stop('Install the Excel reader once with: install.packages("readxl")')
}
if (!file.exists(input_file)) stop("Input workbook not found: ", input_file)
if (!is.numeric(bin_width_deg) || length(bin_width_deg) != 1 ||
    !is.finite(bin_width_deg) || bin_width_deg <= 0 ||
    bin_width_deg > 180 ||
    abs(360 / bin_width_deg - round(360 / bin_width_deg)) > 1e-8) {
  stop("bin_width_deg must be a positive divisor of 360, at most 180.")
}
data <- readxl::read_excel(input_file, sheet = sheet_name)
required <- c("Sample ID", "Signed angle (deg)", "Included",
              "Source review status", "Focus status", "Distinct egg confirmed")
if (!all(required %in% names(data))) {
  stop("Missing columns: ", paste(setdiff(required, names(data)), collapse = ", "))
}
clean <- function(x) tolower(trimws(as.character(x)))
angles <- suppressWarnings(as.numeric(data[["Signed angle (deg)"]]))
included <- clean(data[["Included"]]) %in% "yes"
reviewed <- clean(data[["Source review status"]]) %in% c("edited", "accepted")
confirmed <- clean(data[["Focus status"]]) %in% "clear" &
  clean(data[["Distinct egg confirmed"]]) %in% "yes"
keep <- included & reviewed & is.finite(angles)
if (confirmed_only) keep <- keep & confirmed
selected <- data[keep, , drop = FALSE]
angles <- angles[keep]
if (!length(angles)) stop("No eligible samples for these filter settings.")
if (anyDuplicated(selected[["Sample ID"]])) {
  stop("Duplicate Sample IDs found. Resolve them before plotting.")
}
# Wrap +180 to -180: both are the SAME downward direction.
angles <- ((angles + 180) %% 360) - 180

# Bins are centered on 0, +/-30, ... for the default 30-degree bin width.
# The downward bin wraps across -180/+180 so it is not split into two bars.
nbins <- as.integer(round(360 / bin_width_deg))
centers <- (0:(nbins - 1)) * bin_width_deg
bin_id <- floor(((angles + bin_width_deg / 2) %% 360) / bin_width_deg) + 1L
counts <- tabulate(bin_id, nbins = nbins)
stopifnot(sum(counts) == nrow(selected))

# These coordinates explicitly establish the requested orientation:
# x = radius * sin(angle); y = radius * cos(angle).
xy <- function(deg, radius = 1) {
  rad <- deg * pi / 180
  cbind(x = radius * sin(rad), y = radius * cos(rad))
}
stopifnot(max(abs(xy(c(0, 90, -90, 180)) -
                   rbind(c(0, 1), c(1, 0), c(-1, 0), c(0, -1)))) < 1e-10)

ring_values <- pretty(c(0, max(counts)), n = 4)
ring_values <- unique(ring_values[ring_values > 0 &
                                  ring_values == floor(ring_values)])
if (!length(ring_values) || max(ring_values) < max(counts)) {
  ring_values <- sort(unique(c(ring_values, max(counts))))
}
rmax <- max(ring_values)
degree_label <- function(x) {
  if (x == 0) return("0\u00b0")
  if (abs(x) == 180) return("\u00b1180\u00b0")
  sprintf("%+d\u00b0", x)
}
draw_radial <- function() {
  old <- par(mar = c(3, 2, 5, 2), family = "sans")
  on.exit(par(old))
  plot(NA, xlim = c(-1.28, 1.28) * rmax,
       ylim = c(-1.28, 1.28) * rmax, asp = 1,
       axes = FALSE, xlab = "", ylab = "", bty = "n")
  # Radial HEIGHT is count, not sector area; compare bar lengths.
  for (i in seq_along(counts)) {
    if (counts[i] == 0) next
    arc <- seq(centers[i] - bin_width_deg / 2,
               centers[i] + bin_width_deg / 2, length.out = 80)
    edge <- xy(arc, counts[i])
    polygon(c(0, edge[, 1], 0), c(0, edge[, 2], 0),
            col = "#55A4B9", border = "white", lwd = 1.2)
  }
  circle <- seq(-180, 180, length.out = 721)
  for (rr in ring_values) {
    p <- xy(circle, rr)
    lines(p[, 1], p[, 2], col = "#A9B7C1", lty = 3)
  }
  for (a in seq(-180, 135, 45)) {
    p <- xy(a, rmax)
    segments(0, 0, p[1, 1], p[1, 2], col = "#CBD3D9", lty = 3)
    label <- xy(a, rmax * 1.15)
    text(label[1, 1], label[1, 2], degree_label(a), cex = 1.1)
  }
  # Count labels near the upper-right diagonal.
  for (rr in ring_values) {
    p <- xy(22.5, rr)
    text(p[1, 1], p[1, 2], labels = rr, cex = .8, col = "#253746",
         pos = 4, offset = .25)
  }
  if (show_individual_ticks) {
    inner <- xy(angles, rmax * 1.025)
    outer <- xy(angles, rmax * 1.06)
    segments(inner[, 1], inner[, 2], outer[, 1], outer[, 2],
             col = "#24465C", lwd = 1)
  }
  title(main = "Oil-globule angle distribution", cex.main = 1.4, line = 2.5)
  mode <- if (confirmed_only) "focus + identity confirmed" else "edited/accepted, included samples"
  mtext(sprintf("n = %d | %s | %g-degree bins",
                length(angles), mode, bin_width_deg),
        side = 3, line = .7, cex = .9)
  mtext("Radial height = sample count; outside ticks = individual angles",
        side = 1, line = .3, cex = .85)
  mtext("Zero points upward (opposite downward gravity). Right positive; left negative.",
        side = 1, line = 1.5, cex = .85)
}
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
suffix <- if (confirmed_only) "confirmed" else "included"
stem <- paste0("egg_angle_radial_", suffix)
png_path <- file.path(output_dir, paste0(stem, ".png"))
pdf_path <- file.path(output_dir, paste0(stem, ".pdf"))

grDevices::png(png_path, width = 2100, height = 2100, res = 240, type = "cairo")
tryCatch(draw_radial(), finally = grDevices::dev.off())
grDevices::cairo_pdf(pdf_path, width = 8.75, height = 8.75)
tryCatch(draw_radial(), finally = grDevices::dev.off())
if (interactive()) draw_radial()

cat("Samples plotted:", length(angles), "\n")
cat("Focus + identity confirmed among these:", sum(confirmed[keep]), "\n")
cat("PNG:", normalizePath(png_path, winslash = "/"), "\n")
cat("PDF:", normalizePath(pdf_path, winslash = "/"), "\n")
# Named output remains available in R for inspecting bin counts.
radial_counts <- data.frame(
  angle_center_deg = ((centers + 180) %% 360) - 180,
  sample_count = counts
)
print(radial_counts[order(radial_counts$angle_center_deg), ], row.names = FALSE)

