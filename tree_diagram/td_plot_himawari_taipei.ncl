begin
  infile  = getenv("INFILE")
  outfile = getenv("OUTFILE")

  if (ismissing(infile) .or. infile .eq. "") then
    print("fatal: set environment variable INFILE")
    exit
  end if
  if (ismissing(outfile) .or. outfile .eq. "") then
    outfile = "himawari_taipei_tbb13"
  end if

  lon_min = 121.2
  lon_max = 122.0
  lat_min = 24.8
  lat_max = 25.4

  f   = addfile(infile, "r")
  lat = f->latitude
  lon = f->longitude

  ; short2flt() already applies scale_factor and add_offset from the
  ; variable's attributes. Multiplying again by @scale_factor and adding
  ; @add_offset double-decodes the packed short, compressing the real
  ; 266-292 K range down to ~275.8-276.1 K (a near-constant "empty" map).
  ; Just use short2flt once. Debug prints below confirm the decoded range.
  tbb = short2flt(f->tbb_13)

  print("tbb_13 raw  type=" + typeof(f->tbb_13) + \
        " min=" + min(f->tbb_13) + " max=" + max(f->tbb_13))
  print("tbb_13 decoded min=" + min(tbb) + " max=" + max(tbb) + \
        " mean=" + avg(tbb))

  ilat = ind(lat.ge.lat_min .and. lat.le.lat_max)
  ilon = ind(lon.ge.lon_min .and. lon.le.lon_max)

  if (.not. any(ismissing(ilat)) .and. .not. any(ismissing(ilon))) then
    tbb_tw = tbb(ilat, ilon)
    lat_tw = lat(ilat)
    lon_tw = lon(ilon)
  else
    print("fatal: requested Taipei bbox is outside file domain")
    exit
  end if

  ; Himawari full-disk latitude is stored descending (60 -> -60). ind()
  ; preserves source order, so lat_tw arrives descending and tbb_tw's
  ; first axis follows. gsn_csm_contour with 1D sfYArray expects a
  ; monotone-ascending Y to drive triangulation; a descending Y gives
  ; a valid range in the colour bar but leaves the panel blank.
  ; Flip both the coordinate and the data's first axis to ascending.
  if (lat_tw(0) .gt. lat_tw(dimsizes(lat_tw) - 1)) then
    lat_tw := lat_tw(::-1)
    tbb_tw := tbb_tw(::-1, :)
  end if
  if (lon_tw(0) .gt. lon_tw(dimsizes(lon_tw) - 1)) then
    lon_tw := lon_tw(::-1)
    tbb_tw := tbb_tw(:, ::-1)
  end if
  print("taipei window: nlat=" + dimsizes(lat_tw) + " nlon=" + dimsizes(lon_tw) + \
        " tbb_tw min=" + min(tbb_tw) + " max=" + max(tbb_tw) + " mean=" + avg(tbb_tw))

  wks = gsn_open_wks("png", outfile)
  gsn_define_colormap(wks, "MPL_viridis")

  ; Re-attach ascending coords to tbb_tw so gsn_csm_contour uses the
  ; variable's own named-dimension coordinates (no sfXArray/sfYArray
  ; needed). Clearing any stale coords first avoids the mismatch where
  ; NCL would otherwise see the original descending-order lat/lon
  ; metadata on the subset and silently refuse to render.
  tbb_tw!0 = "latitude"
  tbb_tw!1 = "longitude"
  tbb_tw&latitude  = lat_tw
  tbb_tw&longitude = lon_tw

  res = True
  res@gsnMaximize = True
  res@cnFillOn = True
  res@cnFillMode = "RasterFill"
  res@cnLinesOn = False
  res@cnLineLabelsOn = False
  res@lbLabelBarOn = True
  res@tiMainString = "Himawari-9 TBB13 Taipei Window"
  res@tiXAxisString = "Longitude"
  res@tiYAxisString = "Latitude"

  plot = gsn_csm_contour(wks, tbb_tw, res)
end
