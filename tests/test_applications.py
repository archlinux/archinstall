from archinstall.applications.print_service import PrintServiceApp


def test_print_service_includes_ghostscript() -> None:
	# cups only ships the PDF/PostScript rendering filter through ghostscript,
	# so driverless (IPP Everywhere) printing fails without it.
	assert 'ghostscript' in PrintServiceApp().packages
