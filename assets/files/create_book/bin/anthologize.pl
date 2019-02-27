#!/usr/bin/env perl
#
# Usage: anthologize.pl cdrom anthology volume_id volume_no
#
#    where cdrom is the directory containing the entire CD-ROM and
#    anthology is the directory (which will be created if necessary)
#    that should be sent to the ACL Anthology.
#
# Everything is built entirely off the CD-ROM, using no other files.
# So if the CD-ROM (particularly the bib files) has been hand-edited,
# then the Anthology will follow those edits.
#
# Most of the files in the anthology are just pointers onto the CD-ROM.
# We can follow these links when tarring up the anthology.
# Perhaps the tarball name should have the same base name as the
# bib file at the top level of the CD-ROM.

#####
#print STDOUT "Getting Text::BibTeX (see http://search.cpan.org/~gward/Text-BibTeX-0.34)"
#   wget http://search.cpan.org/CPAN/authors/id/G/GW/GWARD/Text-BibTeX-0.34.tar.gz
#   tar xvf Text-BibTeX-0.34
#   cd Text-BibTeX-0.34
#   perl Makefile.PL
#   make
#   make install

use utf8;
use open qw(:std :utf8);

use strict 'vars';
use File::Spec;
use Text::BibTeX;

my ($cdrom,$anthology,$volume_id,$volume_no,) = @ARGV;

# check ACLPUB path
die "Need to export ACLPUB=/path/to/acl-pub/assets/files/create_book"
  unless(-d $ENV{ACLPUB});

#system("rm -rf $anthology")==0 || die;   # if existing "anthology" outdir exists, remove it and start clean
system("mkdir $anthology")==0 || die;

# anthdir is the new location, e.g., anthology/N/N18
my $anthdir = join("","$anthology/",substr($volume_id, 0, 1),"/$volume_id");

# iterate through directories in ${unzipped_tar_dir}/{acronym}/proceedings
for my $dir (glob("$cdrom/*")) {
  next unless -d "$dir/bib";
  print STDERR "Anthologizing $dir ...\n";

  my $urlprefix; # initially undefined

  # iterate through the bib files
  for my $bib (glob("$dir/bib/*.bib")) {   # bib entry files in numerically sorted order
    chomp($bib);

    # grab the corresponding pdf file in the pdf/ directory
    my $pdf = $bib;
    $pdf =~ s{/bib/([^/]*)\.bib$}{/pdf/$1.pdf};

    # Parse the bib entry.
    my $file = Text::BibTeX::File->new($bib);
    my $bibentry = Text::BibTeX::Entry->new({ binmode => 'utf-8', normalization => 'NFC' }, $file);

    # Extract URL from bib file; translate it to anthology base filename
    warn "Warning: No URL given in $bib (skipping)\n", next unless $bibentry->exists('url');
    my $url = $bibentry->get('url');
    die "Aborting: $url in $bib is not a valid ACL Anthology URL\n"
        unless $url =~ m{^http://www.aclweb.org/anthology/([A-Z])(\d{2})-(\d{0,2})*};

    # anth is the full location with the final characters as the file id, e.g., anthology/N/N18/N18-1001
    # extract the final 4 characters of the url
    my $paper_id=substr $url, -4; # bug: $volume_no should override?
    # test for front matter
    if ($paper_id =~ m/-/) {
      # this will become anthology/N/N18/N18-1000
      $paper_id = $volume_no;
    }

    my $anth = "$anthdir/$volume_id-$paper_id";
    my $anthfile = "$volume_id-$volume_no";

    next if $paper_id eq "";

    if (!defined $urlprefix) {

      # The first bibfile in the directory.  Specially, this is actually an
      # entry for the entire volume corresponding to this directory.  It has
      # a special, shorter URL in this case, such as .../P05-1.

      $urlprefix = $url;    # remember for later
      ## die "Although $bib is first listed file in its dir, it is not numbered 0"
      ##	unless $dir =~ m{/[^/]+$} && $bib =~ m{[A-Z]{3}\d{2}\.bib$};   # e.g., in ACL directory, we'd expect bib/ACL00.bib or something

      # First, create if necessary the anthology directory where all
      # these files will go.

      system("mkdir -p $anthdir")==0 || die;


      ###################################
      # Create the volume-level files in this directory,
      # i.e., $anth.bib for a bib database of all papers in the volume (N18-1.bib)
      # and $anth.pdf for the entire volume (N18-1.pdf)

      my @bibs = glob("$dir/*.bib");
      die "Aborting: No master .bib file exists in $dir\n" if @bibs < 1;
      die "Aborting: Multiple .bib files exist in $dir\n" if @bibs > 1;
      symlink(File::Spec->abs2rel($bibs[0],$anthdir), "$anth.bib") || die "No bib or multiple bibs exist.";

      my @pdfs = glob("$dir/*.pdf");
      die "Aborting: No master .bib file exists in $dir\n" if @bibs < 1;
      die "Aborting: Multiple .bib files exist in $dir\n" if @bibs > 1;
      symlink(File::Spec->abs2rel($pdfs[0],$anthdir), "$anth.pdf") || die;

      ###################################
      # Create the paper-level files in this directory
      # i.e., $anth.bib for a bib database of each individual paper in the volume (N18-1000.bib)
      # and $anth.pdf for the individual paper (e.g., N18-1000.pdf)

      # Now pad $anthfile out with zeroes until it has length 8,
      # e.g., from P05-1 to P05-1000.  The padded version
      # will be used as the anthology names for $bib and $pdf, which correspond
      # respectively to the single bib entry for the book, and the
      # front matter of the book.  (The unpadded version corresponded
      # respectively to a complete bib database for the book, and the entire book.)
      die "Although $bib is first file in its dir, it is not a \@Book entry"
	unless $bibentry->type eq 'book';
      die "Although $bib is first file in its dir, its URL $url already has at least an 8-character filename and can't be padded to give individual paper numbers"
	unless length($anthfile) < 8;
      my $padding = "0" x (8 - length($anthfile));
      $anthfile .= $padding;
      $anth .= $padding;
      $url .= $padding;   # for error messages only -- the version that goes into the XML file will come fresh from $bibentry
      $paper_id .= $padding;
    }

    # Link the current .bib file and its corresponding .pdf file into
    # the anthology.
    die "Aborting: $url in $bib is not an extension of the prefix $urlprefix from the first bib entry"
      unless substr($url,0,length($urlprefix)) eq $urlprefix;
    die "Aborting: $url in $bib does not have an 8-char filename" unless $url =~ m{/[^/]{8}$};

    symlink(File::Spec->abs2rel($bib,$anthdir), "$anth.bib");
    symlink(File::Spec->abs2rel($pdf,$anthdir), "$anth.pdf");

    # Link the additional files (i.e. supplemental) that are in .pdf format, and rename them as ".Notes"
    my $additional_pdf = join("","$dir/additional/$volume_id-$paper_id","_OptionalAttachment.pdf");
    if (-e $additional_pdf) {
      symlink(File::Spec->abs2rel($additional_pdf,$anthdir), join("", $anth, ".Notes.pdf"));
    }

    # Link the additional files (i.e. supplemental) that are in .pdf format, and rename them as ".Additional"
    my @additional_other = glob(join("","$dir/additional/$volume_id-$paper_id","_OptionalAttachment.*"));
    if (-e @additional_other){# and ! $additional_other[0] eq $additional_pdf) {
      print $additional_other[0];
      #symlink(File::Spec->abs2rel($additional_pdf,$anthdir), join("", $anth, ".Attachment.$extension"));
    }
  }
  system("$ENV{ACLPUB}/bin/bib2anth.pl $dir/bib $volume_id $anthdir/$volume_id.xml")==0 || die;
}
